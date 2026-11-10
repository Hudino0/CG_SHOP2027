"""Lanes: cut the region into strips of free height, sweep each strip, route.

The block solver (`fekete`) pays for a fixed grid in both axes and holds a
block in a 64-bit mask, which caps the cutter width. This solver has no
blocks. It works for any cutter width and any cutter shape.

1. **Strips (exact dynamic program).** Cut the rows of the region into
   consecutive strips of at most `H` rows (`H` = cutter height). A strip of
   `h` rows is swept by one horizontal line of centers; the `h` region rows
   meet `h` consecutive rows of the cutter. For one strip the cheapest set of
   center intervals ("lanes") is computed directly (see `_strip`). The
   partition with the least total cost is found by dynamic programming over
   the rows. Both orientations are tried.
2. **Route.** A tour must pass along every lane. This is a travelling
   salesman problem on segments; 2-opt and Or-opt moves run on it, compiled.
3. **k tours.** The single tour is cut into `k` closed tours of balanced
   length, each is improved, and lanes move from the longest tour to the
   others while that lowers the maximum.
4. **Refine.** `refine.Refiner` shortens the walks on the lattice against the
   exact coverage; the travel between lanes also mows, and this step uses it.

Why the result covers the region (steps 1 and 2; step 4 keeps coverage by
its own invariant, and the official validator checks the final tours):

**Lemma (row).** Let a cutter row be the interval of offsets `[lo, hi]`, and
let a horizontal lane hold the centers `a..b` on the line that puts this
cutter row on a region row. The lane sweeps exactly the cells `a+lo .. b+hi`
of that row. So a run of cells `u..v` is swept if `a <= u-lo` and `b >= v-hi`.
If `u-lo > v-hi` (the run is shorter than the cutter row), one center
anywhere in `[v-hi, u-lo]` sweeps the whole run.

*Proof.* Center `c` sweeps `c+lo .. c+hi`. The union over `c = a..b` is an
interval because consecutive centers shift it by one. ∎

For a cutter row with gaps (the X-shaped cutters) the lemma holds for the
hull `[lo, hi]` of the row when the lane is at least as long as the widest
gap; shorter lanes are made that long (`_strip`, `min_length`).

Every region row lies in exactly one strip, and in its strip every run is
swept by the lemma. A tour that walks every lane end to end visits all its
centers. ∎
"""

from __future__ import annotations

import random
import time

import numpy as np
from cgshop2027_pyutils.grid import CellSet
from cgshop2027_pyutils.schemas import CGSHOP2027Solution
from numba import njit

from ..catalog import cutter_cells, region_cells
from ..catalog import validator as make_validator
from ._tour import Point, make_tour
from .refine import Refiner

# The part of the time that goes to the lattice refiner.
REFINE_SHARE = 0.4


# -- step 1: strips ---------------------------------------------------------


def _runs(row: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """First and last column of every run of True in a row."""
    edges = np.diff(np.concatenate(([0], row.astype(np.int8), [0])))
    return np.flatnonzero(edges == 1), np.flatnonzero(edges == -1) - 1


class _Cutter:
    """Row data of the cutter: hull, widest gap, and the rows that exist."""

    def __init__(self, cutter: CellSet) -> None:
        mask = cutter.mask.astype(bool)
        self.height = mask.shape[0]
        self.y0 = cutter.origin[1]
        self.lo = np.zeros(self.height, dtype=np.int64)
        self.hi = np.zeros(self.height, dtype=np.int64)
        self.min_length = 0
        for r in range(self.height):
            cols = np.flatnonzero(mask[r])
            self.lo[r] = cutter.origin[0] + cols[0]
            self.hi[r] = cutter.origin[0] + cols[-1]
            if cols.size > 1:
                self.min_length = max(self.min_length, int(np.diff(cols).max()) - 1)


@njit(cache=True)
def _strip(starts, ends, count, min_length, jump, out):
    """The lanes of one strip from its demands; returns (cost, lanes).

    `starts[i] <= ends[i]` is a core: the lane must hold all of `starts[i] ..
    ends[i]`. `starts[i] > ends[i]` is a point demand: one center anywhere in
    `ends[i] .. starts[i]`. The demands must be sorted by `min(start, end)`.
    Cores are merged; point demands that no lane meets get a center of their
    own, placed greedily (the classic optimal stabbing of intervals, here
    against the lanes that exist). `out[j] = (a, b)` receives the lanes.
    The cost is the lane length plus the walk between lanes, capped at
    `jump`: a far lane is the router's business.
    """
    lanes = 0
    # Pass 1: merge the cores.
    for i in range(count):
        if starts[i] > ends[i]:
            continue
        if lanes > 0 and starts[i] <= out[lanes - 1, 1] + 1:
            if ends[i] > out[lanes - 1, 1]:
                out[lanes - 1, 1] = ends[i]
        else:
            out[lanes, 0] = starts[i]
            out[lanes, 1] = ends[i]
            lanes += 1
    cores = lanes
    # Pass 2: point demands, by right end. A demand [l, r] is met by a core
    # that overlaps it or by the last point placed.
    order = np.empty(count, dtype=np.int64)
    m = 0
    for i in range(count):
        if starts[i] > ends[i]:
            order[m] = i
            m += 1
    if m > 0:
        rights = np.empty(m, dtype=np.int64)
        for t in range(m):
            rights[t] = starts[order[t]]
        order[:m] = order[:m][np.argsort(rights)]
        last = -(1 << 60)
        for t in range(m):
            left = ends[order[t]]
            right = starts[order[t]]
            if last >= left:
                continue
            # The cores are disjoint and sorted: find the first that ends at
            # or after `left`; it meets the demand if it starts by `right`.
            a = 0
            b = cores
            while a < b:
                mid = (a + b) // 2
                if out[mid, 1] < left:
                    a = mid + 1
                else:
                    b = mid
            if a < cores and out[a, 0] <= right:
                continue
            last = right
            out[lanes, 0] = right
            out[lanes, 1] = right
            lanes += 1
    if lanes == 0:
        return 0, 0
    # Sort the lanes by start (the points were appended after the cores).
    if lanes > cores and cores > 0:
        keys = out[:lanes, 0].copy()
        idx = np.argsort(keys)
        tmp = out[:lanes].copy()
        for t in range(lanes):
            out[t, 0] = tmp[idx[t], 0]
            out[t, 1] = tmp[idx[t], 1]
    # Short lanes of a cutter with gaps: stretch to `min_length`.
    if min_length > 0:
        for t in range(lanes):
            short = min_length - (out[t, 1] - out[t, 0])
            if short > 0:
                out[t, 0] -= short // 2
                out[t, 1] += short - short // 2
        w = 0
        for t in range(1, lanes):
            if out[t, 0] <= out[w, 1] + 1:
                if out[t, 1] > out[w, 1]:
                    out[w, 1] = out[t, 1]
            else:
                w += 1
                out[w, 0] = out[t, 0]
                out[w, 1] = out[t, 1]
        lanes = w + 1
    cost = 0
    for t in range(lanes):
        cost += out[t, 1] - out[t, 0]
        if t > 0:
            cost += min(out[t, 0] - out[t - 1, 1], jump)
    return cost, lanes


@njit(cache=True)
def _demands(run_ptr, run_u, run_v, y0, h, lo, hi, r0, starts, ends):
    """Collect the demands of the strip `y0 .. y0+h-1`, sorted by left end."""
    count = 0
    for i in range(h):
        for t in range(run_ptr[y0 + i], run_ptr[y0 + i + 1]):
            starts[count] = run_u[t] - lo[r0 + i]
            ends[count] = run_v[t] - hi[r0 + i]
            count += 1
    keys = np.minimum(starts[:count], ends[:count])
    idx = np.argsort(keys)
    s = starts[:count].copy()
    e = ends[:count].copy()
    for t in range(count):
        starts[t] = s[idx[t]]
        ends[t] = e[idx[t]]
    return count


@njit(cache=True)
def _partition(run_ptr, run_u, run_v, lo, hi, min_length, jump, step_cost):
    """The cheapest cut of the rows into strips. Returns (cost, heights, r0s).

    `best[y]` is the least cost of the rows below `y`. A strip of `h` rows is
    tried with the cutter rows centered (both roundings).
    """
    n = run_ptr.shape[0] - 1
    H = lo.shape[0]
    most = 0
    for y in range(n):
        width = 0
        for i in range(min(H, n - y)):
            width += run_ptr[y + i + 1] - run_ptr[y + i]
        most = max(most, width)
    starts = np.empty(most + 1, dtype=np.int64)
    ends = np.empty(most + 1, dtype=np.int64)
    out = np.empty((most + 1, 2), dtype=np.int64)
    INF = 1 << 60
    best = np.full(n + 1, INF, dtype=np.int64)
    best[0] = 0
    arg_h = np.zeros(n + 1, dtype=np.int64)
    arg_r = np.zeros(n + 1, dtype=np.int64)
    for y in range(1, n + 1):
        if run_ptr[y] == run_ptr[y - 1]:
            # An empty row costs nothing and ends a strip.
            best[y] = best[y - 1]
            arg_h[y] = 1
            continue
        for h in range(1, min(H, y) + 1):
            if best[y - h] >= INF:
                continue
            for r0 in ((H - h) // 2, (H - h + 1) // 2):
                count = _demands(run_ptr, run_u, run_v, y - h, h, lo, hi, r0, starts, ends)
                cost, lanes = _strip(starts, ends, count, min_length, jump, out)
                total = best[y - h] + cost + (step_cost if lanes > 0 else 0)
                if total < best[y]:
                    best[y] = total
                    arg_h[y] = h
                    arg_r[y] = r0
                if (H - h) % 2 == 0:
                    break
    return best[n], arg_h, arg_r


def _lanes(region: CellSet, cutter: CellSet) -> tuple[int, np.ndarray]:
    """The lanes of the best strip partition, as rows `(y, a, b)` of centers."""
    cut = _Cutter(cutter)
    mask = region.mask
    n = mask.shape[0]
    ptr = [0]
    us, vs = [], []
    for y in range(n):
        u, v = _runs(mask[y])
        us.append(u)
        vs.append(v)
        ptr.append(ptr[-1] + len(u))
    run_ptr = np.array(ptr, dtype=np.int64)
    run_u = np.concatenate(us).astype(np.int64) if us else np.zeros(0, dtype=np.int64)
    run_v = np.concatenate(vs).astype(np.int64) if vs else np.zeros(0, dtype=np.int64)
    jump = 2 * cut.height
    cost, arg_h, arg_r = _partition(
        run_ptr, run_u, run_v, cut.lo, cut.hi, cut.min_length, jump, cut.height
    )
    most = int(np.diff(run_ptr).max(initial=0)) * cut.height + 1
    starts = np.empty(most, dtype=np.int64)
    ends = np.empty(most, dtype=np.int64)
    out = np.empty((most, 2), dtype=np.int64)
    lanes = []
    y = n
    ox, oy = region.origin
    while y > 0:
        h, r0 = int(arg_h[y]), int(arg_r[y])
        y -= h
        if run_ptr[y + h] == run_ptr[y]:
            continue
        count = _demands(run_ptr, run_u, run_v, y, h, cut.lo, cut.hi, r0, starts, ends)
        _, found = _strip(starts, ends, count, cut.min_length, jump, out)
        center_y = oy + y - (cut.y0 + r0)
        for t in range(found):
            lanes.append((center_y, ox + int(out[t, 0]), ox + int(out[t, 1])))
    return int(cost), np.array(lanes, dtype=np.int64).reshape(-1, 3)


# -- step 2: a tour over the lanes -------------------------------------------
#
# A tour is `order` (lane ids) and `flip` (1 = walk the lane from b to a).
# `ex, ey` hold the two ends of every lane: index 2*i is the `a` end and
# 2*i + 1 the `b` end. Lane i is entered at end `2*i + flip` and left at the
# other one.


@njit(cache=True)
def _d(ex, ey, p, q):
    return abs(ex[p] - ex[q]) + abs(ey[p] - ey[q])


@njit(cache=True)
def _tour_cost(order, flip, n, ex, ey):
    """The length of the closed tour: the lanes and the links between them."""
    if n == 0:
        return 0
    total = 0
    for i in range(n):
        v = order[i]
        total += abs(ex[2 * v] - ex[2 * v + 1])
        if n > 1:
            w = order[(i + 1) % n]
            total += _d(ex, ey, 2 * v + 1 - flip[i], 2 * w + flip[(i + 1) % n])
    if n == 1:
        total *= 2  # there and back
    return total


@njit(cache=True)
def _two_opt(order, flip, n, ex, ey, near, deadline_checks):
    """2-opt with neighbour lists; reversing a part flips its lanes.

    Returns the total gain. `near[e]` lists lane ends close to end `e`.
    """
    if n < 4:
        return 0
    pos = np.empty(order.max() + 1, dtype=np.int64)
    for i in range(n):
        pos[order[i]] = i
    gained = 0
    improved = True
    rounds = 0
    while improved and rounds < deadline_checks:
        improved = False
        rounds += 1
        for i in range(n):
            v = order[i]
            out_v = 2 * v + 1 - flip[i]
            i1 = i + 1 if i + 1 < n else 0
            in_next = 2 * order[i1] + flip[i1]
            base = _d(ex, ey, out_v, in_next)
            best_gain = 0
            best_j = -1
            for c in range(near.shape[1]):
                e = near[out_v, c]
                if e < 0:
                    break
                d1 = _d(ex, ey, out_v, e)
                if d1 >= base:
                    break
                w = e // 2
                j = pos[w]
                # After the move v's exit joins w's exit, so w must now be
                # left through `e`: that is the case when `e` is w's exit.
                if 2 * w + 1 - flip[j] != e or j == i:
                    continue
                j1 = j + 1 if j + 1 < n else 0
                in_after = 2 * order[j1] + flip[j1]
                gain = base + _d(ex, ey, e, in_after) - d1 - _d(ex, ey, in_next, in_after)
                if gain > best_gain:
                    best_gain = gain
                    best_j = j
            if best_j < 0:
                continue
            # Reverse order[i+1 .. j] (cyclically) and flip those lanes.
            a = i1
            b = best_j
            length = b - a + 1 if b >= a else b - a + 1 + n
            for t in range(length // 2):
                p = (a + t) % n
                q = (b - t) % n
                order[p], order[q] = order[q], order[p]
                fp, fq = flip[p], flip[q]
                flip[p] = 1 - fq
                flip[q] = 1 - fp
                pos[order[p]] = p
                pos[order[q]] = q
            if length % 2 == 1:
                p = (a + length // 2) % n
                flip[p] = 1 - flip[p]
            gained += best_gain
            improved = True
    return gained


@njit(cache=True)
def _or_opt(order, flip, n, ex, ey, near, max_chain, rounds_limit):
    """Move a chain of up to `max_chain` lanes elsewhere, either way round."""
    if n < 5:
        return 0
    gained = 0
    buf = np.empty(n, dtype=np.int64)
    fbuf = np.empty(n, dtype=np.int64)
    pos = np.empty(order.max() + 1, dtype=np.int64)
    rounds = 0
    improved = True
    while improved and rounds < rounds_limit:
        improved = False
        rounds += 1
        for i in range(n):
            pos[order[i]] = i
        i = 0
        while i < n:
            moved = False
            for size in range(1, max_chain + 1):
                if size >= n - 2:
                    break
                # The chain is order[i .. i+size-1]; p before it, q after it.
                ip = (i - 1) % n
                iq = (i + size) % n
                last = (i + size - 1) % n
                p_out = 2 * order[ip] + 1 - flip[ip]
                q_in = 2 * order[iq] + flip[iq]
                c_in = 2 * order[i] + flip[i]
                c_out = 2 * order[last] + 1 - flip[last]
                removed = (_d(ex, ey, p_out, c_in) + _d(ex, ey, c_out, q_in)
                           - _d(ex, ey, p_out, q_in))
                if removed <= 0:
                    continue
                best_gain = 0
                best_at = -1
                best_rev = 0
                for end in (c_in, c_out):
                    for c in range(near.shape[1]):
                        e = near[end, c]
                        if e < 0:
                            break
                        if _d(ex, ey, end, e) >= removed:
                            break
                        w = e // 2
                        j = pos[w]
                        # Skip lanes of the chain itself.
                        off = (j - i) % n
                        if off < size:
                            continue
                        # Insert between j and its successor, or its predecessor and j.
                        for side in range(2):
                            if side == 0:
                                ja = j
                                jb = (j + 1) % n
                            else:
                                ja = (j - 1) % n
                                jb = j
                            if (ja - i) % n < size or (jb - i) % n < size:
                                continue
                            a_out = 2 * order[ja] + 1 - flip[ja]
                            b_in = 2 * order[jb] + flip[jb]
                            link = _d(ex, ey, a_out, b_in)
                            fwd = _d(ex, ey, a_out, c_in) + _d(ex, ey, c_out, b_in) - link
                            rev = _d(ex, ey, a_out, c_out) + _d(ex, ey, c_in, b_in) - link
                            if removed - fwd > best_gain:
                                best_gain = removed - fwd
                                best_at = ja
                                best_rev = 0
                            if removed - rev > best_gain:
                                best_gain = removed - rev
                                best_at = ja
                                best_rev = 1
                if best_at < 0:
                    continue
                # Rebuild: walk from q round to p, dropping the chain in after best_at.
                m = 0
                t = iq
                for _ in range(n - size):
                    buf[m] = order[t]
                    fbuf[m] = flip[t]
                    m += 1
                    if t == best_at:
                        for s in range(size):
                            if best_rev == 0:
                                src = (i + s) % n
                                buf[m] = order[src]
                                fbuf[m] = flip[src]
                            else:
                                src = (i + size - 1 - s) % n
                                buf[m] = order[src]
                                fbuf[m] = 1 - flip[src]
                            m += 1
                    t = (t + 1) % n
                for s in range(n):
                    order[s] = buf[s]
                    flip[s] = fbuf[s]
                    pos[order[s]] = s
                gained += best_gain
                improved = True
                moved = True
                break
            if not moved:
                i += 1
    return gained


def _neighbours(ex: np.ndarray, ey: np.ndarray, members: np.ndarray, count: int = 10) -> np.ndarray:
    """For every lane end of `members`, the nearest ends of other lanes."""
    near = np.full((ex.shape[0], count), -1, dtype=np.int64)
    ends = np.concatenate([2 * members, 2 * members + 1])
    if ends.size <= 2:
        return near
    px, py = ex[ends], ey[ends]
    # Blocks keep the distance matrix small.
    for start in range(0, ends.size, 2048):
        part = slice(start, start + 2048)
        dist = np.abs(px[part, None] - px[None, :]) + np.abs(py[part, None] - py[None, :])
        dist[ends[part, None] // 2 == ends[None, :] // 2] = 1 << 60
        take = min(count, ends.size - 2)
        idx = np.argpartition(dist, take - 1, axis=1)[:, :take]
        rows = np.arange(idx.shape[0])[:, None]
        idx = idx[rows, np.argsort(dist[rows, idx], axis=1)]
        near[ends[part], :take] = ends[idx]
    return near


@njit(cache=True)
def _seed(value):
    np.random.seed(value)


@njit(cache=True)
def _kicks(order, flip, n, ex, ey, near, rounds):
    """Iterated local search: double-bridge kick, 2-opt and Or-opt, keep if not worse.

    The kick cuts the tour at three places close together and swaps the two
    middle parts; no lane changes direction. Returns the gain.
    """
    best = _tour_cost(order, flip, n, ex, ey)
    start = best
    o = order.copy()
    f = flip.copy()
    tmp_o = np.empty(n, dtype=np.int64)
    tmp_f = np.empty(n, dtype=np.int64)
    span = min(n - 1, 50)
    for _ in range(rounds):
        a = np.random.randint(0, n - 3)
        b = min(n - 2, a + 1 + np.random.randint(0, span))
        c = min(n - 1, b + 1 + np.random.randint(0, span))
        if not (a < b < c):
            continue
        # o[0..a] o[b+1..c] o[a+1..b] o[c+1..]
        m = 0
        for t in range(0, a + 1):
            tmp_o[m] = o[t]; tmp_f[m] = f[t]; m += 1
        for t in range(b + 1, c + 1):
            tmp_o[m] = o[t]; tmp_f[m] = f[t]; m += 1
        for t in range(a + 1, b + 1):
            tmp_o[m] = o[t]; tmp_f[m] = f[t]; m += 1
        for t in range(c + 1, n):
            tmp_o[m] = o[t]; tmp_f[m] = f[t]; m += 1
        for t in range(n):
            o[t] = tmp_o[t]; f[t] = tmp_f[t]
        while True:
            gain = _two_opt(o, f, n, ex, ey, near, 8)
            gain += _or_opt(o, f, n, ex, ey, near, 3, 8)
            if gain == 0:
                break
        cost = _tour_cost(o, f, n, ex, ey)
        if cost <= best:
            best = cost
            for t in range(n):
                order[t] = o[t]; flip[t] = f[t]
        else:
            for t in range(n):
                o[t] = order[t]; f[t] = flip[t]
    return start - best


def _improve(order, flip, ex, ey, deadline: float, kicks: bool = True) -> None:
    """2-opt and Or-opt to a local optimum, then kicks until the deadline."""
    n = len(order)
    if n < 4:
        return
    near = _neighbours(ex, ey, order)
    while time.perf_counter() < deadline:
        gain = _two_opt(order, flip, n, ex, ey, near, 8)
        gain += _or_opt(order, flip, n, ex, ey, near, 3, 8)
        if gain == 0:
            break
    if not kicks or n < 8:
        return
    batch = 16
    while (now := time.perf_counter()) < deadline:
        _kicks(order, flip, n, ex, ey, near, batch)
        spent = time.perf_counter() - now
        # Batches of about 50 ms keep the deadline close.
        batch = max(1, min(4 * batch, int(batch * 0.05 / max(spent, 1e-4))))


def _serpentine(lanes: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Strip after strip, turning at each strip end."""
    keys = np.lexsort((lanes[:, 1], lanes[:, 0]))
    order, flip = [], []
    forward = True
    y = None
    row: list[int] = []

    def flush() -> None:
        nonlocal forward
        if not row:
            return
        order.extend(row if forward else row[::-1])
        flip.extend([0 if forward else 1] * len(row))
        forward = not forward

    for i in keys.tolist():
        if y is not None and lanes[i, 0] != y:
            flush()
            row = []
        y = lanes[i, 0]
        row.append(i)
    flush()
    return np.array(order, dtype=np.int64), np.array(flip, dtype=np.int64)


def _comb(lanes: np.ndarray, k: int, piece: int) -> tuple[np.ndarray, list]:
    """Cut the lanes at `2k - 1` seams and give every cutter two columns.

    A cutter goes up its left column strip by strip and comes down its right
    column, so its tour closes where it began: no walk back across the
    region. The seams are quantiles of the lane length, so the `k` tours get
    equal lane length. Lanes are cut at the seams (and into pieces of at most
    `piece`); the two parts of a cut lane are one step apart.
    Returns the new lanes and, per cutter, `(order, flip)`.
    """
    columns = 2 * k
    lengths = lanes[:, 2] - lanes[:, 1] + 1
    xs = np.repeat(lanes[:, 1], 2)
    xs[1::2] = lanes[:, 2]
    # Seams: positions where the cumulated lane length reaches i / columns.
    grid = np.arange(int(lanes[:, 1].min()), int(lanes[:, 2].max()) + 2)
    covered = np.zeros(grid.size + 1, dtype=np.int64)
    np.add.at(covered, lanes[:, 1] - grid[0], 1)
    np.add.at(covered, lanes[:, 2] + 1 - grid[0], -1)
    density = np.cumsum(np.cumsum(covered)[:-1])
    seams = [int(grid[0] + np.searchsorted(density, density[-1] * i / columns)) + 1
             for i in range(1, columns)]
    cut: list[tuple[int, int, int, int]] = []  # (column, y, a, b)
    for y, a, b in lanes.tolist():
        bounds = [a, *[x for x in seams if a < x <= b], b + 1]
        for lo, hi in zip(bounds, bounds[1:]):
            column = sum(1 for x in seams if x <= lo)
            pieces = max(1, -(-(hi - lo) // piece))
            for i in range(pieces):
                first = lo + (hi - lo) * i // pieces
                last = lo + (hi - lo) * (i + 1) // pieces - 1
                cut.append((column, y, first, last))
    new = np.array([(y, a, b) for _, y, a, b in cut], dtype=np.int64).reshape(-1, 3)
    by_column: list[list[int]] = [[] for _ in range(columns)]
    for index, (column, _, _, _) in enumerate(cut):
        by_column[column].append(index)
    parts = []
    for robot in range(k):
        order: list[int] = []
        flip: list[int] = []
        for side, upward in ((2 * robot, True), (2 * robot + 1, False)):
            members = by_column[side]
            if not members:
                continue
            sub_order, sub_flip = _serpentine(new[members])
            sub_order = np.array(members, dtype=np.int64)[sub_order]
            if not upward:
                sub_order, sub_flip = sub_order[::-1], 1 - sub_flip[::-1]
            order.extend(sub_order.tolist())
            flip.extend(sub_flip.tolist())
        parts.append((np.array(order, dtype=np.int64), np.array(flip, dtype=np.int64)))
    return new, [part for part in parts if len(part[0])]


# -- step 3: k tours ----------------------------------------------------------


def _split(order, flip, ex, ey, k: int) -> list[tuple[np.ndarray, np.ndarray]]:
    """Cut the closed tour into at most `k` closed tours, least maximum first."""
    n = len(order)
    if k <= 1 or n <= 1:
        return [(order, flip)]
    if n <= k:
        return [(order[i : i + 1].copy(), flip[i : i + 1].copy()) for i in range(n)]
    best = None
    for start in sorted(set(np.linspace(0, n - 1, min(n, 48)).astype(int).tolist())):
        o = np.roll(order, -start)
        f = np.roll(flip, -start)
        lane = np.abs(ex[2 * o] - ex[2 * o + 1])
        out_end = 2 * o + 1 - f
        in_end = 2 * o + f
        link = np.abs(ex[out_end[:-1]] - ex[in_end[1:]]) + np.abs(ey[out_end[:-1]] - ey[in_end[1:]])
        # prefix[i] = length of lanes 0..i-1 and of the links between them.
        prefix = np.concatenate(([0], np.cumsum(lane)))
        prefix[2:] += np.cumsum(link)

        def closed(i: int, j: int) -> int:
            """Closed length of the chunk i..j (inclusive)."""
            inner = prefix[j + 1] - prefix[i] - (link[i - 1] if i > 0 else 0)
            if i == j:
                return int(2 * lane[i])
            back = abs(ex[out_end[j]] - ex[in_end[i]]) + abs(ey[out_end[j]] - ey[in_end[i]])
            return int(inner + back)

        def cuts(limit: int) -> list[int] | None:
            sizes, at = [], 0
            while at < n:
                if len(sizes) == k or closed(at, at) > limit:
                    return None
                low, high = at, n - 1
                while low < high:
                    middle = (low + high + 1) // 2
                    if closed(at, middle) <= limit:
                        low = middle
                    else:
                        high = middle - 1
                sizes.append(low - at + 1)
                at = low + 1
            return sizes

        low, high = 0, int(2 * prefix[-1]) + 1
        found = None
        while low <= high:
            middle = (low + high) // 2
            sizes = cuts(middle)
            if sizes is None:
                low = middle + 1
            else:
                found, high = (middle, sizes), middle - 1
        if found and (best is None or found[0] < best[0]):
            best = (found[0], o, f, found[1])
    _, o, f, sizes = best
    parts, at = [], 0
    for size in sizes:
        parts.append((o[at : at + size].copy(), f[at : at + size].copy()))
        at += size
    return parts


@njit(cache=True)
def _best_insertion(v, order, flip, n, ex, ey):
    """Cheapest place and direction for lane `v` in a tour: (delta, at, flip)."""
    lane = abs(ex[2 * v] - ex[2 * v + 1])
    if n == 0:
        return 2 * lane, 0, 0
    if n == 1:
        w = order[0]
        other = abs(ex[2 * w] - ex[2 * w + 1])
        best = 1 << 60
        best_f = 0
        for f in range(2):
            there = _d(ex, ey, 2 * w + 1 - flip[0], 2 * v + f)
            back = _d(ex, ey, 2 * v + 1 - f, 2 * w + flip[0])
            if there + back < best:
                best = there + back
                best_f = f
        return lane + best - other, 0, best_f
    best = 1 << 60
    best_at = 0
    best_f = 0
    for i in range(n):
        j = i + 1 if i + 1 < n else 0
        a_out = 2 * order[i] + 1 - flip[i]
        b_in = 2 * order[j] + flip[j]
        link = _d(ex, ey, a_out, b_in)
        for f in range(2):
            delta = _d(ex, ey, a_out, 2 * v + f) + _d(ex, ey, 2 * v + 1 - f, b_in) - link
            if delta < best:
                best = delta
                best_at = i
                best_f = f
    return lane + best, best_at, best_f


def _balance(parts, ex, ey, deadline: float) -> list[tuple[np.ndarray, np.ndarray]]:
    """Move single lanes out of the longest tour while the maximum drops."""
    tours = [(o.copy(), f.copy()) for o, f in parts]
    costs = [_tour_cost(o, f, len(o), ex, ey) for o, f in tours]
    while time.perf_counter() < deadline and len(tours) > 1:
        worst = max(range(len(tours)), key=costs.__getitem__)
        o, f = tours[worst]
        n = len(o)
        if n <= 1:
            break
        best = None
        for i in range(n):
            if n > 2:
                p, q = (i - 1) % n, (i + 1) % n
                lighter = costs[worst] - (
                    abs(ex[2 * o[i]] - ex[2 * o[i] + 1])
                    + _d(ex, ey, 2 * o[p] + 1 - f[p], 2 * o[i] + f[i])
                    + _d(ex, ey, 2 * o[i] + 1 - f[i], 2 * o[q] + f[q])
                    - _d(ex, ey, 2 * o[p] + 1 - f[p], 2 * o[q] + f[q])
                )
            else:
                rest = np.delete(o, i)
                lighter = _tour_cost(rest, np.delete(f, i), 1, ex, ey)
            if lighter >= costs[worst]:
                continue
            for other in range(len(tours)):
                if other == worst:
                    continue
                oo, ff = tours[other]
                delta, at, way = _best_insertion(int(o[i]), oo, ff, len(oo), ex, ey)
                peak = max(lighter, costs[other] + delta)
                if peak < costs[worst] and (best is None or peak < best[0]):
                    best = (peak, i, other, at, way)
        if best is None:
            break
        _, i, other, at, way = best
        v = o[i]
        oo, ff = tours[other]
        tours[other] = (np.insert(oo, at + 1 if len(oo) else 0, v),
                        np.insert(ff, at + 1 if len(ff) else 0, way))
        tours[worst] = (np.delete(o, i), np.delete(f, i))
        for index in (worst, other):
            costs[index] = _tour_cost(*tours[index], len(tours[index][0]), ex, ey)
    return tours


# -- the solver ---------------------------------------------------------------


def _waypoints(order, flip, lanes) -> list[Point]:
    points: list[Point] = []
    for v, f in zip(order.tolist(), flip.tolist()):
        y, a, b = (int(t) for t in lanes[v])
        points.extend([(b, y), (a, y)] if f else [(a, y), (b, y)])
    return points


def _corner_path(points: list[Point]) -> list[Point]:
    """Join the waypoints by axis-parallel moves (vertical first) and close."""
    if not points:
        return []
    path = [points[0]]
    for x, y in [*points[1:], points[0]]:
        px, py = path[-1]
        if px != x and py != y:
            path.append((px, y))
        if (x, y) != path[-1]:
            path.append((x, y))
    if len(path) > 1 and path[-1] == path[0]:
        path.pop()
    return path


def _transpose(cells: CellSet) -> CellSet:
    return CellSet(np.ascontiguousarray(cells.mask.T), (cells.origin[1], cells.origin[0]))


def _ends(lanes: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    ex = np.empty(2 * len(lanes), dtype=np.int64)
    ey = np.empty(2 * len(lanes), dtype=np.int64)
    ex[0::2], ex[1::2] = lanes[:, 1], lanes[:, 2]
    ey[0::2] = ey[1::2] = lanes[:, 0]
    return ex, ey


def _settle(parts, ex, ey, deadline: float):
    """Improve the longest tour, balance, and repeat until the deadline."""
    began = time.perf_counter()
    budget = deadline - began
    for o, f in parts:
        _improve(o, f, ex, ey, deadline, kicks=False)
    costs = [int(_tour_cost(o, f, len(o), ex, ey)) for o, f in parts]
    turn = 0
    while time.perf_counter() < deadline:
        longest = max(range(len(parts)), key=costs.__getitem__)
        until = min(deadline, time.perf_counter() + max(0.05, budget / 12))
        o, f = parts[longest]
        _improve(o, f, ex, ey, until)
        if len(parts) > 1:
            parts = _balance(parts, ex, ey, deadline)
        costs = [int(_tour_cost(o, f, len(o), ex, ey)) for o, f in parts]
        turn += 1
    return parts, costs


def _route(lanes: np.ndarray, k: int, piece: int, deadline: float):
    """Steps 2 and 3 for one set of lanes, from two starts; the best wins.

    Returns the lanes as cut, the tours, their lengths and the start's name.
    """
    began = time.perf_counter()
    budget = deadline - began
    results = []

    # Start 1, "comb": two columns per cutter, closed by construction.
    cut, parts = _comb(lanes, k, piece)
    ex, ey = _ends(cut)
    parts, lengths = _settle(parts, ex, ey, began + 0.5 * budget)
    results.append((max(lengths), "comb", cut, parts, lengths))

    # Start 2, "serpentine": one tour over all lanes, then cut into k.
    cut, _ = _comb(lanes, 1, piece)
    ex, ey = _ends(cut)
    order, flip = _serpentine(cut)
    _improve(order, flip, ex, ey, began + (0.75 if k > 1 else 1.0) * budget)
    if k > 1:
        parts, lengths = _settle(_split(order, flip, ex, ey, k), ex, ey, deadline)
    else:
        parts, lengths = [(order, flip)], [int(_tour_cost(order, flip, len(order), ex, ey))]
    results.append((max(lengths), "serpentine", cut, parts, lengths))

    _, name, cut, parts, lengths = min(results, key=lambda r: r[0])
    return cut, parts, lengths, name, {r[1]: r[0] for r in results}


def solve(instance, time_limit: float = 30.0, seed: int = 0, refine: bool = True) -> CGSHOP2027Solution:
    """Strip partition by dynamic programming, lane routing, lattice refinement."""
    began = time.perf_counter()
    region = region_cells(instance)
    cutter = cutter_cells(instance)
    k = instance.number_of_cutters
    uid = instance.instance_uid
    rng = random.Random(seed)
    _seed(seed)
    if len(region) == 0:
        return CGSHOP2027Solution(instance_uid=uid, tours=[make_tour([(0, 0)])] * k,
                                  meta={"algorithm": "lanes"})
    validator = make_validator(instance)
    offsets = list(cutter.cells())
    route_until = began + time_limit * (1 - REFINE_SHARE if refine else 1.0)

    best = None
    tried = {}
    for name in ("rows", "columns"):
        flipped = name == "columns"
        reg = _transpose(region) if flipped else region
        cut = _transpose(cutter) if flipped else cutter
        estimate, lanes = _lanes(reg, cut)
        share = (route_until - time.perf_counter()) / (2 if name == "rows" else 1)
        piece = 3 * max(cutter.width, cutter.height)
        lanes, parts, lengths, start, starts = _route(
            lanes, k, piece, time.perf_counter() + max(share, 0.05)
        )
        paths = [_corner_path(_waypoints(o, f, lanes)) for o, f in parts]
        if flipped:
            paths = [[(y, x) for x, y in path] for path in paths]
        tried[name] = {"lanes": len(lanes), "estimate": estimate, "starts": starts,
                       "start": start, "max": max(lengths)}
        if best is None or max(lengths) < best[0]:
            best = (max(lengths), name, paths)
    _, chosen, paths = best
    meta = {"algorithm": "lanes", "orientation": chosen, "tried": tried}

    def as_solution(paths) -> CGSHOP2027Solution:
        tours = [make_tour(path) for path in paths if path]
        park = paths[0][0] if paths and paths[0] else (0, 0)
        tours.extend(make_tour([park]) for _ in range(k - len(tours)))
        return CGSHOP2027Solution(instance_uid=uid, tours=tours, meta=meta)

    solution = as_solution(paths)
    if refine and not validator.check_for_errors(solution):
        refiner = Refiner(region.mask, region.origin, offsets, [p for p in paths if p])
        refiner.run(began + time_limit, rng)
        candidate = as_solution(refiner.paths())
        if not validator.check_for_errors(candidate):
            meta["unrefined"] = solution.max_tour_length
            solution = candidate
    meta["seconds"] = round(time.perf_counter() - began, 1)
    return solution.model_copy(update={"meta": meta})
