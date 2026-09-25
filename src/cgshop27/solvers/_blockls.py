"""Compiled kernels for the block solver in `fekete.py`.

The block solver spends nearly all its time in two places: finding puzzle
pieces (`_Pieces._search`) and the local search over the block tour (`_Ring`
and `_lns`). Both are ported here to numba, move for move, so the solver
does the same search many times faster.

- `piece_table` computes the length of every puzzle piece a model can ask
  for: each block content times each pair of sides. Block contents and
  sweeps are bit masks of `s * s` bits, as in `_Pieces`.
- `optimize` and `lns` run 2-opt, Or-opt and the large neighbourhood search
  on a tour given as an array of block ids.

The graph arrays travel as one tuple `G = (bx, by, mid, table, s, near4,
near8, grid)`; the tour as `t` (block ids), `pos` (index in `t`, or -1) and
`size` (a one-element array, since the LNS changes the tour's length).
"""

from __future__ import annotations

import numpy as np
from numba import njit

BIG = 1 << 40
L, R, B, T, J = range(5)


# -- puzzle pieces -------------------------------------------------------------


@njit(cache=True)
def _leg(ax, ay, bx, by, choice, seg_h, seg_v):
    """The cells swept from a to b; an L goes vertical first if choice is 0."""
    if ax == bx:
        return seg_v[ax, min(ay, by), max(ay, by)]
    if ay == by:
        return seg_h[ay, min(ax, bx), max(ax, bx)]
    if choice == 0:
        return seg_v[ax, min(ay, by), max(ay, by)] | seg_h[by, min(ax, bx), max(ax, bx)]
    return seg_h[ay, min(ax, bx), max(ax, bx)] | seg_v[bx, min(ay, by), max(ay, by)]


@njit(cache=True)
def _covers(rx, ry, nr, mask, stamp, seg_h, seg_v):
    legs = nr - 1
    for combo in range(1 << legs):
        bits = stamp[ry[0], rx[0]]
        for i in range(legs):
            bits |= _leg(rx[i], ry[i], rx[i + 1], ry[i + 1], (combo >> i) & 1, seg_h, seg_v)
        if bits & mask == mask:
            return True
    return False


@njit(cache=True)
def _piece(mask, pair, ex, ey, a, b, cx, cy, center, order1, len1, order2, len2,
           stamp, seg_h, seg_v, rx, ry):
    """Length of the shortest covering route with 0, 1 or 2 inner points."""
    rx[0] = ex[a]
    ry[0] = ey[a]
    rx[1] = ex[b]
    ry[1] = ey[b]
    if _covers(rx, ry, 2, mask, stamp, seg_h, seg_v):
        return abs(ex[a] - ex[b]) + abs(ey[a] - ey[b])
    count = cx.shape[0]
    best = -1
    for k in range(count):
        q = order1[pair, k]
        if q != center and stamp[cy[q], cx[q]] & mask == 0:
            continue
        rx[1] = cx[q]
        ry[1] = cy[q]
        rx[2] = ex[b]
        ry[2] = ey[b]
        if _covers(rx, ry, 3, mask, stamp, seg_h, seg_v):
            best = len1[pair, k]
            break
    for k in range(count * count):
        length = len2[pair, k]
        if best >= 0 and length >= best:
            break
        index = order2[pair, k]
        first = index // count
        second = index % count
        if first == second:
            continue
        if first != center and stamp[cy[first], cx[first]] & mask == 0:
            continue
        if second != center and stamp[cy[second], cx[second]] & mask == 0:
            continue
        rx[1] = cx[first]
        ry[1] = cy[first]
        rx[2] = cx[second]
        ry[2] = cy[second]
        rx[3] = ex[b]
        ry[3] = ey[b]
        if _covers(rx, ry, 4, mask, stamp, seg_h, seg_v):
            return length
    return best


@njit(cache=True)
def _piece_table(masks, pairs, ex, ey, cx, cy, center, order1, len1, order2, len2,
                 stamp, seg_h, seg_v):
    table = np.full((masks.shape[0], 5, 5), -1, dtype=np.int64)
    rx = np.empty(4, dtype=np.int64)
    ry = np.empty(4, dtype=np.int64)
    for m in range(masks.shape[0]):
        for p in range(pairs.shape[0]):
            a = pairs[p, 0]
            b = pairs[p, 1]
            length = _piece(masks[m], p, ex, ey, a, b, cx, cy, center, order1, len1,
                            order2, len2, stamp, seg_h, seg_v, rx, ry)
            table[m, a, b] = length
            table[m, b, a] = length
    return table


def piece_table(pieces, masks: list[int]) -> np.ndarray:
    """Piece lengths for every block content and pair of sides; -1 = unknown.

    `pieces` is a `fekete._Pieces`. Its window, ends and center fix the
    candidates; `-1` marks the rare contents that need `_Pieces._greedy`.
    """
    s = pieces.s
    points = list(dict.fromkeys([*pieces.window, pieces.center]))
    ends = [pieces.ends[side] for side in range(5)]
    everything = points + ends
    x0 = min(p[0] for p in everything)
    y0 = min(p[1] for p in everything)
    width = max(p[0] for p in everything) - x0 + 1
    height = max(p[1] for p in everything) - y0 + 1

    stamp = np.zeros((height, width), dtype=np.int64)
    for y in range(height):
        for x in range(width):
            stamp[y, x] = pieces.stamp((x + x0, y + y0))
    seg_h = np.zeros((height, width, width), dtype=np.int64)
    for y in range(height):
        for a in range(width):
            bits = 0
            for b in range(a, width):
                bits |= int(stamp[y, b])
                seg_h[y, a, b] = bits
    seg_v = np.zeros((width, height, height), dtype=np.int64)
    for x in range(width):
        for a in range(height):
            bits = 0
            for b in range(a, height):
                bits |= int(stamp[b, x])
                seg_v[x, a, b] = bits

    cx = np.array([p[0] - x0 for p in points], dtype=np.int64)
    cy = np.array([p[1] - y0 for p in points], dtype=np.int64)
    ex = np.array([p[0] - x0 for p in ends], dtype=np.int64)
    ey = np.array([p[1] - y0 for p in ends], dtype=np.int64)
    center = points.index(pieces.center)
    pairs = np.array([(a, b) for a in range(5) for b in range(a, 5)], dtype=np.int64)
    count = len(points)
    order1 = np.empty((len(pairs), count), dtype=np.int64)
    len1 = np.empty((len(pairs), count), dtype=np.int64)
    order2 = np.empty((len(pairs), count * count), dtype=np.int64)
    len2 = np.empty((len(pairs), count * count), dtype=np.int64)
    between = np.abs(cx[:, None] - cx[None, :]) + np.abs(cy[:, None] - cy[None, :])
    for p, (a, b) in enumerate(pairs):
        to_q = np.abs(cx - ex[a]) + np.abs(cy - ey[a])
        from_q = np.abs(cx - ex[b]) + np.abs(cy - ey[b])
        one = to_q + from_q
        order = np.argsort(one, kind="stable")
        order1[p], len1[p] = order, one[order]
        two = (to_q[:, None] + between + from_q[None, :]).ravel()
        order = np.argsort(two, kind="stable")
        order2[p], len2[p] = order, two[order]
    mask_array = np.array(masks, dtype=np.int64)
    return _piece_table(mask_array, pairs, ex, ey, cx, cy, center, order1, len1,
                        order2, len2, stamp, seg_h, seg_v)


# -- the tour --------------------------------------------------------------------


@njit(cache=True)
def _side(G, v, u):
    bx, by = G[0], G[1]
    dx = bx[u] - bx[v]
    dy = by[u] - by[v]
    if dy == 0:
        if dx == -1:
            return L
        if dx == 1:
            return R
    elif dx == 0:
        if dy == -1:
            return B
        if dy == 1:
            return T
    return J


@njit(cache=True)
def _bc(G, v, u, w):
    return G[3][G[2][v], _side(G, v, u), _side(G, v, w)]


@njit(cache=True)
def _ec(G, u, v):
    steps = abs(G[0][u] - G[0][v]) + abs(G[1][u] - G[1][v])
    return 0 if steps == 1 else G[4] * steps


@njit(cache=True)
def _succ(t, pos, size, v):
    i = pos[v] + 1
    return t[i] if i < size[0] else t[0]


@njit(cache=True)
def _pred(t, pos, size, v):
    i = pos[v] - 1
    return t[i] if i >= 0 else t[size[0] - 1]


@njit(cache=True)
def tour_cost(G, t, size):
    n = size[0]
    total = 0
    for i in range(n):
        v = t[i]
        u = t[i - 1] if i > 0 else t[n - 1]
        w = t[i + 1] if i + 1 < n else t[0]
        total += _bc(G, v, u, w) + _ec(G, v, w)
    return total


@njit(cache=True)
def order_cost(G, order):
    """The cost of a closed tour given as an array of at least 3 blocks."""
    size = np.array([order.shape[0]], dtype=np.int64)
    return tour_cost(G, order, size)


@njit(cache=True)
def _delta(G, t, pos, size, ra, rb, nr, aa, ab, na, verts, nb, nbc):
    """Cost change of swapping edges, or BIG if the move is malformed."""
    nv = 0
    for e in range(nr + na):
        for flip in range(2):
            if e < nr:
                a = ra[e] if flip == 0 else rb[e]
                b = rb[e] if flip == 0 else ra[e]
            else:
                a = aa[e - nr] if flip == 0 else ab[e - nr]
                b = ab[e - nr] if flip == 0 else aa[e - nr]
            i = -1
            for k in range(nv):
                if verts[k] == a:
                    i = k
                    break
            if i < 0:
                i = nv
                verts[nv] = a
                nb[nv, 0] = _pred(t, pos, size, a)
                nb[nv, 1] = _succ(t, pos, size, a)
                nbc[nv] = 2
                nv += 1
            if e < nr:
                k = -1
                for j in range(nbc[i]):
                    if nb[i, j] == b:
                        k = j
                        break
                if k < 0:
                    return BIG
                nb[i, k] = nb[i, nbc[i] - 1]
                nbc[i] -= 1
            else:
                if nbc[i] >= 2:
                    return BIG
                nb[i, nbc[i]] = b
                nbc[i] += 1
    change = 0
    for e in range(na):
        change += _ec(G, aa[e], ab[e])
    for e in range(nr):
        change -= _ec(G, ra[e], rb[e])
    for i in range(nv):
        if nbc[i] != 2:
            return BIG
        v = verts[i]
        change += _bc(G, v, nb[i, 0], nb[i, 1]) - _bc(G, v, _pred(t, pos, size, v), _succ(t, pos, size, v))
    return change


@njit(cache=True)
def _reverse(t, pos, size, i, j):
    n = size[0]
    m = (j - i) % n + 1
    if 2 * m > n:
        i, j, m = (j + 1) % n, (i - 1) % n, n - m
    for _ in range(m // 2):
        a = t[i]
        b = t[j]
        t[i] = b
        t[j] = a
        pos[b] = i
        pos[a] = j
        i = i + 1 if i + 1 < n else 0
        j = j - 1 if j > 0 else n - 1


@njit(cache=True)
def _move2(t, pos, size, a, b, c, d):
    """Replace the edges (a, b) and (c, d) by (a, c) and (b, d)."""
    if _succ(t, pos, size, a) == b:
        _reverse(t, pos, size, pos[b], pos[c])
    else:
        _reverse(t, pos, size, pos[a], pos[d])


@njit(cache=True)
def _improve(G, t, pos, size, a, work, touched):
    """First improving 2-opt or Or-opt move around `a`: (touched, change)."""
    near4, near8 = G[5], G[6]
    ra, rb, aa, ab, verts, nbc, run = work[0], work[1], work[2], work[3], work[4], work[5], work[6]
    nb = np.empty((6, 3), dtype=np.int64)
    for k in range(near8.shape[1]):
        b = near8[a, k]
        if b < 0 or pos[b] < 0 or b == a:
            continue
        a2 = _succ(t, pos, size, a)
        b2 = _succ(t, pos, size, b)
        if b != a2 and b2 != a:
            ra[0], rb[0], ra[1], rb[1] = a, a2, b, b2
            aa[0], ab[0], aa[1], ab[1] = a, b, a2, b2
            change = _delta(G, t, pos, size, ra, rb, 2, aa, ab, 2, verts, nb, nbc)
            if change < 0:
                _move2(t, pos, size, a, a2, b, b2)
                touched[0], touched[1], touched[2], touched[3] = a, a2, b, b2
                return 4, change
        a1 = _pred(t, pos, size, a)
        b1 = _pred(t, pos, size, b)
        if b != a1 and b1 != a:
            ra[0], rb[0], ra[1], rb[1] = a1, a, b1, b
            aa[0], ab[0], aa[1], ab[1] = a1, b1, a, b
            change = _delta(G, t, pos, size, ra, rb, 2, aa, ab, 2, verts, nb, nbc)
            if change < 0:
                _move2(t, pos, size, a1, a, b1, b)
                touched[0], touched[1], touched[2], touched[3] = a, a1, b, b1
                return 4, change

    for run_size in range(1, 4):
        if size[0] < run_size + 4:
            break
        for forward in range(1, -1, -1):
            if run_size == 1 and forward == 0:
                continue
            run[0] = a
            for k in range(1, run_size):
                run[k] = _succ(t, pos, size, run[k - 1]) if forward else _pred(t, pos, size, run[k - 1])
            if forward:
                s1, s2 = run[0], run[run_size - 1]
            else:
                s1, s2 = run[run_size - 1], run[0]
            p = _pred(t, pos, size, s1)
            nn = _succ(t, pos, size, s2)
            for k in range(near4.shape[1]):
                b = near4[a, k]
                if b < 0 or pos[b] < 0:
                    continue
                inside = False
                for r in range(run_size):
                    if run[r] == b:
                        inside = True
                if inside:
                    continue
                for which in range(2):
                    if which == 0:
                        c, d = b, _succ(t, pos, size, b)
                    else:
                        c, d = _pred(t, pos, size, b), b
                    bad = d == p
                    for r in range(run_size):
                        if run[r] == c or run[r] == d:
                            bad = True
                    if bad:
                        continue
                    for flip in range(2 if run_size > 1 else 1):
                        ra[0], rb[0], ra[1], rb[1], ra[2], rb[2] = p, s1, s2, nn, c, d
                        aa[0], ab[0] = p, nn
                        if flip:
                            aa[1], ab[1], aa[2], ab[2] = c, s2, s1, d
                        else:
                            aa[1], ab[1], aa[2], ab[2] = c, s1, s2, d
                        change = _delta(G, t, pos, size, ra, rb, 3, aa, ab, 3, verts, nb, nbc)
                        if change < 0:
                            _move2(t, pos, size, p, s1, c, d)
                            if c != nn:
                                _move2(t, pos, size, p, c, nn, s2)
                            if not flip:
                                _move2(t, pos, size, c, s2, s1, d)
                            touched[0], touched[1], touched[2] = p, nn, c
                            touched[3], touched[4], touched[5] = d, s1, s2
                            return 6, change
    return 0, 0


@njit(cache=True)
def _workspace():
    work = np.empty((7, 6), dtype=np.int64)
    return work


@njit(cache=True)
def _optimize(G, t, pos, size, seeds, nseeds, waiting, queue, max_moves):
    """Queue-driven local search; returns the total cost removed."""
    n_all = waiting.shape[0]
    cap = queue.shape[0]
    head = 0
    tail = 0
    for i in range(nseeds):
        v = seeds[i]
        if not waiting[v]:
            waiting[v] = True
            queue[tail % cap] = v
            tail += 1
    work = _workspace()
    touched = np.empty(6, dtype=np.int64)
    saved = 0
    moves = 0
    while head < tail and moves < max_moves:
        a = queue[head % cap]
        head += 1
        waiting[a] = False
        if pos[a] < 0:
            continue
        count, change = _improve(G, t, pos, size, a, work, touched)
        if count:
            saved -= change
            moves += 1
            for k in range(count):
                v = touched[k]
                if not waiting[v] and tail - head < cap:
                    waiting[v] = True
                    queue[tail % cap] = v
                    tail += 1
    while head < tail:
        waiting[queue[head % cap]] = False
        head += 1
    return saved


@njit(cache=True)
def _bad_seeds(G, t, pos, size):
    n = size[0]
    out = np.empty(n, dtype=np.int64)
    m = 0
    s = G[4]
    for i in range(n):
        v = t[i]
        u = _pred(t, pos, size, v)
        w = _succ(t, pos, size, v)
        if _bc(G, v, u, w) > s or _ec(G, u, v) > 0 or _ec(G, v, w) > 0:
            out[m] = v
            m += 1
    return out, m


@njit(cache=True)
def optimize_all(G, t, pos, size, max_moves):
    """`_Ring.optimize` without seeds: start from every badly placed block."""
    if size[0] < 8:
        return 0
    seeds, m = _bad_seeds(G, t, pos, size)
    waiting = np.zeros(pos.shape[0], dtype=np.bool_)
    queue = np.empty(4 * pos.shape[0] + 16, dtype=np.int64)
    return _optimize(G, t, pos, size, seeds, m, waiting, queue, max_moves)


@njit(cache=True)
def _removal(G, t, pos, size, v):
    u = _pred(t, pos, size, v)
    w = _succ(t, pos, size, v)
    return (
        _ec(G, u, w) - _ec(G, u, v) - _ec(G, v, w) - _bc(G, v, u, w)
        + _bc(G, u, _pred(t, pos, size, u), w) - _bc(G, u, _pred(t, pos, size, u), v)
        + _bc(G, w, u, _succ(t, pos, size, w)) - _bc(G, w, v, _succ(t, pos, size, w))
    )


@njit(cache=True)
def _insertion(G, t, pos, size, v, c, d):
    return (
        _ec(G, c, v) + _ec(G, v, d) - _ec(G, c, d) + _bc(G, v, c, d)
        + _bc(G, c, _pred(t, pos, size, c), v) - _bc(G, c, _pred(t, pos, size, c), d)
        + _bc(G, d, v, _succ(t, pos, size, d)) - _bc(G, d, c, _succ(t, pos, size, d))
    )


@njit(cache=True)
def _remove(t, pos, size, v):
    at = pos[v]
    pos[v] = -1
    n = size[0]
    for i in range(at, n - 1):
        t[i] = t[i + 1]
        pos[t[i]] = i
    size[0] = n - 1


@njit(cache=True)
def _insert(t, pos, size, v, c):
    """Put `v` right after `c`."""
    at = pos[c] + 1
    n = size[0]
    for i in range(n, at, -1):
        t[i] = t[i - 1]
        pos[t[i]] = i
    t[at] = v
    pos[v] = at
    size[0] = n + 1


@njit(cache=True)
def seed_rng(seed):
    np.random.seed(seed)


@njit(cache=True)
def lns(G, t, pos, size, iterations):
    """`fekete._lns` for a fixed number of iterations; returns the gain."""
    if size[0] < 12:
        return 0
    bx, by, near8, grid = G[0], G[1], G[6], G[7]
    n_all = pos.shape[0]
    waiting = np.zeros(n_all, dtype=np.bool_)
    queue = np.empty(4 * n_all + 16, dtype=np.int64)
    snapshot = np.empty(t.shape[0], dtype=np.int64)
    window = np.empty(49, dtype=np.int64)
    seeds = np.empty(3 * 49, dtype=np.int64)
    gained = 0
    for _ in range(iterations):
        n = size[0]
        v = t[np.random.randint(n)]
        radius = np.random.randint(1, 4)
        nw = 0
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                x = bx[v] + dx
                y = by[v] + dy
                if 0 <= y < grid.shape[0] and 0 <= x < grid.shape[1]:
                    w = grid[y, x]
                    if w >= 0 and pos[w] >= 0:
                        window[nw] = w
                        nw += 1
        if nw > n - 8:
            continue
        snapshot[:n] = t[:n]
        change = 0
        for i in range(nw):
            change += _removal(G, t, pos, size, window[i])
            _remove(t, pos, size, window[i])
        for i in range(nw - 1, 0, -1):
            j = np.random.randint(i + 1)
            window[i], window[j] = window[j], window[i]
        for i in range(nw):
            w = window[i]
            best = BIG
            best_x = -1
            for k in range(near8.shape[1]):
                c = near8[w, k]
                if c < 0 or pos[c] < 0:
                    continue
                for which in range(2):
                    if which == 0:
                        x, y = c, _succ(t, pos, size, c)
                    else:
                        x, y = _pred(t, pos, size, c), c
                    step = _insertion(G, t, pos, size, w, x, y)
                    if step < best:
                        best = step
                        best_x = x
            if best_x < 0:
                c = t[0]
                for which in range(2):
                    if which == 0:
                        x, y = c, _succ(t, pos, size, c)
                    else:
                        x, y = _pred(t, pos, size, c), c
                    step = _insertion(G, t, pos, size, w, x, y)
                    if step < best:
                        best = step
                        best_x = x
            change += best
            _insert(t, pos, size, w, best_x)
        ns = 0
        for i in range(nw):
            w = window[i]
            seeds[ns] = w
            seeds[ns + 1] = _pred(t, pos, size, w)
            seeds[ns + 2] = _succ(t, pos, size, w)
            ns += 3
        change -= _optimize(G, t, pos, size, seeds, ns, waiting, queue, 1 << 30)
        if change > 0:
            for i in range(size[0]):
                pos[t[i]] = -1
            size[0] = n
            t[:n] = snapshot[:n]
            for i in range(n):
                pos[t[i]] = i
        else:
            gained -= change
    return gained


class Tour:
    """A tour over the blocks of one model, kept in compiled-friendly arrays."""

    def __init__(self, G, n_all: int, order: list[int]) -> None:
        self.G = G
        self.t = np.zeros(n_all + 1, dtype=np.int64)
        self.pos = np.full(n_all, -1, dtype=np.int64)
        self.size = np.array([len(order)], dtype=np.int64)
        self.t[: len(order)] = order
        self.pos[np.array(order, dtype=np.int64)] = np.arange(len(order))

    def order(self) -> list[int]:
        return self.t[: self.size[0]].tolist()

    def cost(self) -> int:
        return int(tour_cost(self.G, self.t, self.size))

    def optimize(self) -> int:
        return int(optimize_all(self.G, self.t, self.pos, self.size, 1 << 40))

    def lns(self, iterations: int) -> int:
        return int(lns(self.G, self.t, self.pos, self.size, iterations))
