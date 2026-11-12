"""Exact-coverage local search on the lattice walks of a finished solution.

The block solvers think in blocks and pieces; the verifier thinks in lattice
points. This pass works where the verifier works. Each tour is expanded into
its unit steps, and a counter holds, for every cell, how many step points of
all tours sweep it. Two moves shorten a tour and keep the counter above zero on
every region cell:

- **Shortcut.** Drop the points strictly inside a window of the tour and join
  its ends by an L. Valid when no region cell depends on the dropped points.
- **Reroute.** Drop the points inside a window between two corners and join
  the ends by the shortest walk with at most three corners that sweeps every
  region cell that only the dropped points swept. This slides a lane toward
  the border, trims a detour around a hole, and moves a U-turn inward.

Only the tours that decide the objective need to shrink, but a shorter tour
elsewhere is free to take work later, so every tour is improved, the longest
first.
"""

from __future__ import annotations

import random
import time

import numpy as np
from numba import njit

from ._tour import Point


def expand(path: list[Point]) -> np.ndarray:
    """The closed tour as its unit-step points, without the repeated start."""
    out = []
    n = len(path)
    for i in range(n):
        (ax, ay), (bx, by) = path[i], path[(i + 1) % n]
        sx = (bx > ax) - (bx < ax)
        sy = (by > ay) - (by < ay)
        x, y = ax, ay
        while (x, y) != (bx, by):
            out.append((x, y))
            x += sx
            y += sy
    if not out:
        out = [path[0]]
    return np.array(out, dtype=np.int64)


def compress(points: np.ndarray) -> list[Point]:
    """The corner points of a closed unit-step walk."""
    n = len(points)
    if n <= 2:
        return [tuple(map(int, p)) for p in points]
    keep = []
    for i in range(n):
        p, q, r = points[i - 1], points[i], points[(i + 1) % n]
        if (q[0] - p[0], q[1] - p[1]) != (r[0] - q[0], r[1] - q[1]):
            keep.append((int(q[0]), int(q[1])))
    return keep or [(int(points[0][0]), int(points[0][1]))]


# -- kernels ------------------------------------------------------------------


@njit(cache=True)
def _stamp(cnt, reg, x, y, ox, oy, sign):
    """Add a point's sweep to the counter; return how many region cells hit 0."""
    zero = 0
    for k in range(ox.shape[0]):
        cx, cy = x + ox[k], y + oy[k]
        cnt[cy, cx] += sign
        if sign < 0 and cnt[cy, cx] == 0 and reg[cy, cx]:
            zero += 1
    return zero


@njit(cache=True)
def _seed_kernel(value):
    np.random.seed(value)


@njit(cache=True)
def _stamp_all(cnt, P, ox, oy):
    """Add the sweep of every point of a walk to the counter."""
    for i in range(P.shape[0]):
        x, y = P[i, 0], P[i, 1]
        for k in range(ox.shape[0]):
            cnt[y + oy[k], x + ox[k]] += 1


@njit(cache=True)
def _lwalk(ax, ay, bx, by, vertical_first, out, start):
    """Write the points strictly between a and b of an L walk; return count."""
    m = start
    x, y = ax, ay
    if vertical_first:
        sy = 1 if by > y else -1
        while y != by:
            y += sy
            if x == bx and y == by:
                return m - start
            out[m, 0] = x
            out[m, 1] = y
            m += 1
    sx = 1 if bx > x else -1
    while x != bx:
        x += sx
        if x == bx and y == by:
            return m - start
        out[m, 0] = x
        out[m, 1] = y
        m += 1
    sy = 1 if by > y else -1
    while y != by:
        y += sy
        if x == bx and y == by:
            return m - start
        out[m, 0] = x
        out[m, 1] = y
        m += 1
    return m - start


@njit(cache=True)
def _shortcut_pass(P, cnt, reg, ox, oy, window):
    """One sweep of the shortcut move along the whole tour (no wrap-around)."""
    n = P.shape[0]
    out = np.empty((n, 2), dtype=np.int64)
    buf = np.empty((4 * window + 8, 2), dtype=np.int64)
    m = 0
    i = 0
    gained = 0
    while i < n:
        out[m, 0] = P[i, 0]
        out[m, 1] = P[i, 1]
        m += 1
        best_j = -1
        best_gain = 0
        deficit = 0
        j = i + 1
        # Remove P[i+1], P[i+2], ... one by one while no region cell opens up.
        while j < n - 1 and j - i <= window:
            deficit += _stamp(cnt, reg, P[j, 0], P[j, 1], ox, oy, -1)
            if deficit > 0:
                break
            jj = j + 1
            d = abs(P[jj, 0] - P[i, 0]) + abs(P[jj, 1] - P[i, 1])
            g = (jj - i) - d
            if g > best_gain:
                best_gain = g
                best_j = jj
            j += 1
        # Undo the trial removals.
        for t in range(i + 1, j + 1 if deficit > 0 else j):
            if t < n:
                _stamp(cnt, reg, P[t, 0], P[t, 1], ox, oy, 1)
        if best_j < 0:
            i += 1
            continue
        for t in range(i + 1, best_j):
            _stamp(cnt, reg, P[t, 0], P[t, 1], ox, oy, -1)
        k = _lwalk(P[i, 0], P[i, 1], P[best_j, 0], P[best_j, 1], True, buf, 0)
        for t in range(k):
            _stamp(cnt, reg, buf[t, 0], buf[t, 1], ox, oy, 1)
            out[m, 0] = buf[t, 0]
            out[m, 1] = buf[t, 1]
            m += 1
        gained += best_gain
        i = best_j
    return out[:m].copy(), gained


@njit(cache=True)
def _seg_covers(qx, qy, x0, y0, x1, y1, rrun, rcnt, crun, ccnt, cy0, cx0):
    """Does the axis-parallel segment (x0,y0)-(x1,y1) sweep cell (qx, qy)?

    `rrun[r, j] = (lo, hi)` are the runs of cutter row `r` (offsets in x),
    `rcnt[r]` their number; `crun`, `ccnt` the same for the columns. A center
    `x` on the segment sweeps the cell through run `j` when `qx - x` lies in
    the run, that is `x` in `[qx - hi, qx - lo]`. The test is exact for any
    cutter shape.
    """
    if y0 == y1:
        dy = qy - y0 - cy0
        if dy < 0 or dy >= rcnt.shape[0]:
            return False
        lo = min(x0, x1)
        hi = max(x0, x1)
        for j in range(rcnt[dy]):
            if qx - rrun[dy, j, 1] <= hi and qx - rrun[dy, j, 0] >= lo:
                return True
        return False
    dx = qx - x0 - cx0
    if dx < 0 or dx >= ccnt.shape[0]:
        return False
    lo = min(y0, y1)
    hi = max(y0, y1)
    for j in range(ccnt[dx]):
        if qy - crun[dx, j, 1] <= hi and qy - crun[dx, j, 0] >= lo:
            return True
    return False


@njit(cache=True)
def _walk_covers(qs, nq, wx, wy, nw, rrun, rcnt, crun, ccnt, cy0, cx0):
    for q in range(nq):
        ok = False
        for s in range(nw - 1):
            if _seg_covers(qs[q, 0], qs[q, 1], wx[s], wy[s], wx[s + 1], wy[s + 1],
                           rrun, rcnt, crun, ccnt, cy0, cx0):
                ok = True
                break
        if not ok:
            # Move the failing cell to the front: it fails the next try too.
            if q > 0:
                t0 = qs[q, 0]
                t1 = qs[q, 1]
                qs[q, 0] = qs[0, 0]
                qs[q, 1] = qs[0, 1]
                qs[0, 0] = t0
                qs[0, 1] = t1
            return False
    return True


@njit(cache=True)
def _best_walk(ax, ay, bx, by, limit, qs, nq, bx0, by0, bx1, by1,
               rrun, rcnt, crun, ccnt, cy0, cx0, res, ties):
    """Shortest walk a -> b with <= 3 corners, below `limit`, sweeping all qs.

    The walks are a, (ax, t), (u, t), (u, by), b (vertical first) and the mirror
    a, (t, ay), (t, u), (bx, u), b. `t` and `u` range over the box. Writes the
    five points into res and returns the length, or -1.

    With `ties` a walk as long as `limit` is accepted too, and one of the
    shortest walks is drawn at random. Such a move gains nothing, but it lets
    a lane or a U-turn drift, and a later move may then gain.
    """
    wx = np.empty(5, dtype=np.int64)
    wy = np.empty(5, dtype=np.int64)
    best = limit
    found = -1
    seen = 0
    for mode in range(2):
        for t in range(by0 if mode == 0 else bx0, (by1 if mode == 0 else bx1) + 1):
            if mode == 0:
                base = abs(ay - t) + abs(t - by)
            else:
                base = abs(ax - t) + abs(t - bx)
            if base + (abs(ax - bx) if mode == 0 else abs(ay - by)) >= best + ties:
                continue
            lo = bx0 if mode == 0 else by0
            hi = bx1 if mode == 0 else by1
            for u in range(lo, hi + 1):
                if mode == 0:
                    length = base + abs(u - ax) + abs(bx - u)
                else:
                    length = base + abs(u - ay) + abs(by - u)
                if length >= best + ties:
                    continue
                if mode == 0:
                    wx[0] = ax; wy[0] = ay
                    wx[1] = ax; wy[1] = t
                    wx[2] = u; wy[2] = t
                    wx[3] = u; wy[3] = by
                    wx[4] = bx; wy[4] = by
                else:
                    wx[0] = ax; wy[0] = ay
                    wx[1] = t; wy[1] = ay
                    wx[2] = t; wy[2] = u
                    wx[3] = bx; wy[3] = u
                    wx[4] = bx; wy[4] = by
                if _walk_covers(qs, nq, wx, wy, 5, rrun, rcnt, crun, ccnt, cy0, cx0):
                    if length == best and found >= 0:
                        # One more walk of the best length: keep it with
                        # probability 1 / (number seen).
                        seen += 1
                        if np.random.randint(0, seen) != 0:
                            continue
                    else:
                        seen = 1
                    best = length
                    found = length
                    for s in range(5):
                        res[s, 0] = wx[s]
                        res[s, 1] = wy[s]
    return found


@njit(cache=True)
def _reroute_pass(P, cnt, reg, ox, oy, rrun, rcnt, crun, ccnt, cy0, cx0,
                  corners, max_segments, qmax, pad, ties):
    """Try the reroute move on windows that start and end at corners."""
    n = P.shape[0]
    out = np.empty((n, 2), dtype=np.int64)
    qs = np.empty((qmax, 2), dtype=np.int64)
    res = np.empty((5, 2), dtype=np.int64)
    bufcap = 4 * n + 16
    buf = np.empty((bufcap, 2), dtype=np.int64)
    ext = 0
    for k in range(ox.shape[0]):
        ext = max(ext, abs(ox[k]), abs(oy[k]))
    m = 0
    gained = 0
    c = 0
    nc = corners.shape[0]
    i = 0
    while i < n:
        # Advance to the next corner at or after i.
        while c < nc and corners[c] < i:
            c += 1
        if c >= nc or corners[c] != i:
            out[m, 0] = P[i, 0]
            out[m, 1] = P[i, 1]
            m += 1
            i += 1
            continue
        out[m, 0] = P[i, 0]
        out[m, 1] = P[i, 1]
        m += 1
        applied = False
        for r in range(max_segments, 0, -1):
            if c + r >= nc:
                continue
            j = corners[c + r]
            if j >= n or j - i < 2:
                continue
            # Take the interior out and collect the cells that open up.
            nq = 0
            over = False
            for t in range(i + 1, j):
                x = P[t, 0]
                y = P[t, 1]
                for k in range(ox.shape[0]):
                    cx = x + ox[k]
                    cy = y + oy[k]
                    cnt[cy, cx] -= 1
                    if cnt[cy, cx] == 0 and reg[cy, cx]:
                        if nq < qmax:
                            qs[nq, 0] = cx
                            qs[nq, 1] = cy
                            nq += 1
                        else:
                            over = True
            ok = False
            length = -1
            if not over:
                ax = P[i, 0]; ay = P[i, 1]; bx = P[j, 0]; by = P[j, 1]
                x0 = min(ax, bx); x1 = max(ax, bx); y0 = min(ay, by); y1 = max(ay, by)
                for q in range(nq):
                    x0 = min(x0, qs[q, 0] - ext); x1 = max(x1, qs[q, 0] + ext)
                    y0 = min(y0, qs[q, 1] - ext); y1 = max(y1, qs[q, 1] + ext)
                x0 = max(x0, pad); y0 = max(y0, pad)
                x1 = min(x1, reg.shape[1] - 1 - pad); y1 = min(y1, reg.shape[0] - 1 - pad)
                length = _best_walk(ax, ay, bx, by, j - i, qs, nq, x0, y0, x1, y1,
                                    rrun, rcnt, crun, ccnt, cy0, cx0, res, ties)
                ok = length >= 0
            if not ok:
                for t in range(i + 1, j):
                    _stamp(cnt, reg, P[t, 0], P[t, 1], ox, oy, 1)
                continue
            # Write the new interior: the four legs and the corners between.
            nb = 0
            for s in range(4):
                nb += _lwalk(res[s, 0], res[s, 1], res[s + 1, 0], res[s + 1, 1], True, buf, nb)
                if s < 3:
                    buf[nb, 0] = res[s + 1, 0]
                    buf[nb, 1] = res[s + 1, 1]
                    nb += 1
            # Drop immediate repeats (legs of length zero).
            w = 0
            px = P[i, 0]
            py = P[i, 1]
            for t in range(nb):
                if buf[t, 0] == px and buf[t, 1] == py:
                    continue
                buf[w, 0] = buf[t, 0]
                buf[w, 1] = buf[t, 1]
                px = buf[w, 0]
                py = buf[w, 1]
                w += 1
            if w > 0 and buf[w - 1, 0] == P[j, 0] and buf[w - 1, 1] == P[j, 1]:
                w -= 1
            for t in range(w):
                _stamp(cnt, reg, buf[t, 0], buf[t, 1], ox, oy, 1)
                out[m, 0] = buf[t, 0]
                out[m, 1] = buf[t, 1]
                m += 1
            gained += (j - i) - (w + 1)
            i = j
            applied = True
            break
        if not applied:
            i += 1
    return out[:m].copy(), gained


# -- moving work between tours -------------------------------------------------


@njit(cache=True)
def _find_transfer(A, B, la, lb, reach, stride):
    """The best part `A[i..j]` to hand from the longer tour A to tour B.

    B takes the part between `B[ib]` and `B[ib + 1]`; A joins `A[i - 1]` and
    `A[j + 1]` directly. The points of the part stay visited, so the coverage
    cannot break: this move only trades length. Returns `(peak, i, j, ib)`
    with the least `peak = max(new A, new B)`, or peak = -1 if none is below
    `la`.
    """
    n = A.shape[0]
    nb = B.shape[0]
    # A grid over the points of B, for "which point of B is near here".
    x0 = min(A[:, 0].min(), B[:, 0].min())
    y0 = min(A[:, 1].min(), B[:, 1].min())
    gx = (max(A[:, 0].max(), B[:, 0].max()) - x0) // reach + 1
    gy = (max(A[:, 1].max(), B[:, 1].max()) - y0) // reach + 1
    head = np.full(gx * gy, -1, dtype=np.int64)
    nxt = np.empty(nb, dtype=np.int64)
    for t in range(nb):
        c = ((B[t, 1] - y0) // reach) * gx + (B[t, 0] - x0) // reach
        nxt[t] = head[c]
        head[c] = t
    want = (la - lb) // 2
    lo = max(2, want // 4)
    hi = max(lo + 1, min(n - 4, 2 * want))
    best = -1
    bi = 0
    bj = 0
    bb = 0
    i = 1
    while i < n - 3:
        # The point of B nearest to A[i], among the cells around it.
        cx = (A[i, 0] - x0) // reach
        cy = (A[i, 1] - y0) // reach
        near = -1
        dist = 1 << 60
        for yy in range(max(cy - 1, 0), min(cy + 2, gy)):
            for xx in range(max(cx - 1, 0), min(cx + 2, gx)):
                t = head[yy * gx + xx]
                while t >= 0:
                    d = abs(B[t, 0] - A[i, 0]) + abs(B[t, 1] - A[i, 1])
                    if d < dist:
                        dist = d
                        near = t
                    t = nxt[t]
        if near < 0 or dist > 2 * reach or dist == 0:
            i += stride
            continue
        nb1 = near + 1 if near + 1 < nb else 0
        for j in range(i + lo, min(n - 2, i + hi)):
            m = j - i
            back = abs(A[j, 0] - B[nb1, 0]) + abs(A[j, 1] - B[nb1, 1])
            if back > 4 * reach or back == 0:
                continue
            join = abs(A[i - 1, 0] - A[j + 1, 0]) + abs(A[i - 1, 1] - A[j + 1, 1])
            if join == 0:
                continue
            new_a = la - (m + 2) + join
            new_b = lb + dist + m + back - 1
            peak = max(new_a, new_b)
            if peak < la and (best < 0 or peak < best):
                best = peak
                bi = i
                bj = j
                bb = near
        i += stride
    return best, bi, bj, bb


@njit(cache=True)
def _link(a, b, out, m, cnt, ox, oy):
    """Append the points strictly between a and b (an L walk); count them in."""
    buf = np.empty((abs(a[0] - b[0]) + abs(a[1] - b[1]) + 2, 2), dtype=np.int64)
    k = _lwalk(a[0], a[1], b[0], b[1], True, buf, 0)
    for t in range(k):
        out[m, 0] = buf[t, 0]
        out[m, 1] = buf[t, 1]
        m += 1
        for c in range(ox.shape[0]):
            cnt[buf[t, 1] + oy[c], buf[t, 0] + ox[c]] += 1
    return m


@njit(cache=True)
def _apply_transfer(A, B, i, j, ib, cnt, ox, oy):
    """The two walks after the transfer; the new link points are counted in."""
    n = A.shape[0]
    nb = B.shape[0]
    ib1 = ib + 1 if ib + 1 < nb else 0
    new_a = np.empty((n + 2, 2), dtype=np.int64)
    m = 0
    for t in range(0, i):
        new_a[m, 0] = A[t, 0]
        new_a[m, 1] = A[t, 1]
        m += 1
    m = _link(A[i - 1], A[j + 1], new_a, m, cnt, ox, oy)
    for t in range(j + 1, n):
        new_a[m, 0] = A[t, 0]
        new_a[m, 1] = A[t, 1]
        m += 1
    new_a = new_a[:m].copy()
    size = nb + (j - i + 1) + abs(B[ib, 0] - A[i, 0]) + abs(B[ib, 1] - A[i, 1]) \
        + abs(A[j, 0] - B[ib1, 0]) + abs(A[j, 1] - B[ib1, 1]) + 4
    new_b = np.empty((size, 2), dtype=np.int64)
    m = 0
    for t in range(0, ib + 1):
        new_b[m, 0] = B[t, 0]
        new_b[m, 1] = B[t, 1]
        m += 1
    m = _link(B[ib], A[i], new_b, m, cnt, ox, oy)
    for t in range(i, j + 1):
        new_b[m, 0] = A[t, 0]
        new_b[m, 1] = A[t, 1]
        m += 1
    m = _link(A[j], B[ib1], new_b, m, cnt, ox, oy)
    for t in range(ib + 1, nb):
        new_b[m, 0] = B[t, 0]
        new_b[m, 1] = B[t, 1]
        m += 1
    return new_a, new_b[:m].copy()


@njit(cache=True)
def _find_exchange(A, B, la, lb, reach, most):
    """The best swap of a part of A for a part of B (the longer tour is A).

    A gives `A[i..j]` and takes `B[p..q]`, forward or reversed. Both tours
    keep all points between them, so the coverage cannot break. The tours
    must run side by side near both ends of the parts; such places come from
    a grid over the points of B. Returns `(peak, i, j, p, q, reversed)`.
    """
    n = A.shape[0]
    nb = B.shape[0]
    x0 = min(A[:, 0].min(), B[:, 0].min())
    y0 = min(A[:, 1].min(), B[:, 1].min())
    gx = (max(A[:, 0].max(), B[:, 0].max()) - x0) // reach + 1
    gy = (max(A[:, 1].max(), B[:, 1].max()) - y0) // reach + 1
    head = np.full(gx * gy, -1, dtype=np.int64)
    nxt = np.empty(nb, dtype=np.int64)
    for t in range(nb):
        c = ((B[t, 1] - y0) // reach) * gx + (B[t, 0] - x0) // reach
        nxt[t] = head[c]
        head[c] = t
    # Places where A passes near B: (index in A, index in B).
    stride = max(1, n // most)
    pa = np.empty(n // stride + 2, dtype=np.int64)
    pb = np.empty(n // stride + 2, dtype=np.int64)
    count = 0
    i = 2
    while i < n - 2:
        cx = (A[i, 0] - x0) // reach
        cy = (A[i, 1] - y0) // reach
        near = -1
        dist = 1 << 60
        for yy in range(max(cy - 1, 0), min(cy + 2, gy)):
            for xx in range(max(cx - 1, 0), min(cx + 2, gx)):
                t = head[yy * gx + xx]
                while t >= 0:
                    d = abs(B[t, 0] - A[i, 0]) + abs(B[t, 1] - A[i, 1])
                    if d < dist and 2 <= t < nb - 2:
                        dist = d
                        near = t
                    t = nxt[t]
        if near >= 0 and dist <= 2 * reach:
            pa[count] = i
            pb[count] = near
            count += 1
        i += stride
    best = -1
    bi = bj = bp = bq = brev = 0
    for k in range(count):
        i = pa[k]
        for l in range(k + 1, count):
            j = pa[l]
            if j - i < 2:
                continue
            if pb[k] < pb[l]:
                p = pb[k]
                q = pb[l]
                rev = 0
                d1 = abs(A[i - 1, 0] - B[p, 0]) + abs(A[i - 1, 1] - B[p, 1])
                d2 = abs(B[q, 0] - A[j + 1, 0]) + abs(B[q, 1] - A[j + 1, 1])
                d3 = abs(B[p - 1, 0] - A[i, 0]) + abs(B[p - 1, 1] - A[i, 1])
                d4 = abs(A[j, 0] - B[q + 1, 0]) + abs(A[j, 1] - B[q + 1, 1])
            elif pb[k] > pb[l]:
                p = pb[l]
                q = pb[k]
                rev = 1
                d1 = abs(A[i - 1, 0] - B[q, 0]) + abs(A[i - 1, 1] - B[q, 1])
                d2 = abs(B[p, 0] - A[j + 1, 0]) + abs(B[p, 1] - A[j + 1, 1])
                d3 = abs(B[p - 1, 0] - A[j, 0]) + abs(B[p - 1, 1] - A[j, 1])
                d4 = abs(A[i, 0] - B[q + 1, 0]) + abs(A[i, 1] - B[q + 1, 1])
            else:
                continue
            if d1 == 0 or d2 == 0 or d3 == 0 or d4 == 0:
                continue
            new_a = la - (j - i + 2) + (q - p) + d1 + d2
            new_b = lb - (q - p + 2) + (j - i) + d3 + d4
            peak = max(new_a, new_b)
            if peak < la and (best < 0 or peak < best):
                best = peak
                bi = i
                bj = j
                bp = p
                bq = q
                brev = rev
    return best, bi, bj, bp, bq, brev


@njit(cache=True)
def _apply_exchange(A, B, i, j, p, q, rev, cnt, ox, oy):
    """The two walks after the swap; the four links are counted in."""
    n = A.shape[0]
    nb = B.shape[0]
    new_a = np.empty((n + nb + 8 * (cnt.shape[0] + cnt.shape[1]), 2), dtype=np.int64)
    new_b = np.empty((n + nb + 8 * (cnt.shape[0] + cnt.shape[1]), 2), dtype=np.int64)
    m = 0
    for t in range(0, i):
        new_a[m, 0] = A[t, 0]
        new_a[m, 1] = A[t, 1]
        m += 1
    first = q if rev else p
    last = p if rev else q
    m = _link(A[i - 1], B[first], new_a, m, cnt, ox, oy)
    for s in range(q - p + 1):
        t = q - s if rev else p + s
        new_a[m, 0] = B[t, 0]
        new_a[m, 1] = B[t, 1]
        m += 1
    m = _link(B[last], A[j + 1], new_a, m, cnt, ox, oy)
    for t in range(j + 1, n):
        new_a[m, 0] = A[t, 0]
        new_a[m, 1] = A[t, 1]
        m += 1
    ma = m
    m = 0
    for t in range(0, p):
        new_b[m, 0] = B[t, 0]
        new_b[m, 1] = B[t, 1]
        m += 1
    first = j if rev else i
    last = i if rev else j
    m = _link(B[p - 1], A[first], new_b, m, cnt, ox, oy)
    for s in range(j - i + 1):
        t = j - s if rev else i + s
        new_b[m, 0] = A[t, 0]
        new_b[m, 1] = A[t, 1]
        m += 1
    m = _link(A[last], B[q + 1], new_b, m, cnt, ox, oy)
    for t in range(q + 1, nb):
        new_b[m, 0] = B[t, 0]
        new_b[m, 1] = B[t, 1]
        m += 1
    return new_a[:ma].copy(), new_b[:m].copy()


# -- large neighbourhood search: inject anchors, refine around them -----------


@njit(cache=True)
def _nearest(P, runs, pts, dist):
    """For every point of `pts` the distance to the nearest walk point in `runs`."""
    for a in range(pts.shape[0]):
        best = 1 << 40
        for r in range(runs.shape[0]):
            for t in range(runs[r, 0], runs[r, 1] + 1):
                d = abs(P[t, 0] - pts[a, 0]) + abs(P[t, 1] - pts[a, 1])
                if d < best:
                    best = d
        dist[a] = best


@njit(cache=True)
def _inject(P, runs, pts, cnt, ox, oy):
    """Visit every point of `pts` by a walk out and back from the nearest tour point.

    Only the parts `runs` of the walk (index ranges near the window) are
    searched. The tour gets longer and sweeps more; the refiner then decides
    what to keep. Returns the new walk; the new points are counted in.
    """
    n = P.shape[0]
    runs = runs.copy()
    reach = np.empty(pts.shape[0], dtype=np.int64)
    _nearest(P, runs, pts, reach)
    total = n + 2 * int(reach.sum()) + 2 * pts.shape[0]
    out = np.empty((total, 2), dtype=np.int64)
    out[:n] = P
    m = n
    buf = np.empty((int(reach.max()) + 2, 2), dtype=np.int64)
    for a in range(pts.shape[0]):
        best = 1 << 40
        i = -1
        where = 0
        for r in range(runs.shape[0]):
            for t in range(runs[r, 0], runs[r, 1] + 1):
                d = abs(out[t, 0] - pts[a, 0]) + abs(out[t, 1] - pts[a, 1])
                if d < best:
                    best = d
                    i = t
                    where = r
        if i < 0 or best == 0 or best > reach[a]:
            # Earlier detours only bring the tour closer, so this cannot
            # happen; the guard keeps the buffer sizes honest.
            continue
        k = _lwalk(out[i, 0], out[i, 1], pts[a, 0], pts[a, 1], True, buf, 0)
        extra = 2 * k + 2
        out[i + 1 + extra : m + extra] = out[i + 1 : m].copy()
        pos = i + 1
        for t in range(k):
            out[pos] = buf[t]
            pos += 1
        out[pos, 0] = pts[a, 0]
        out[pos, 1] = pts[a, 1]
        pos += 1
        for t in range(k - 1, -1, -1):
            out[pos] = buf[t]
            pos += 1
        out[pos] = out[i]
        for t in range(i + 1, i + 1 + extra):
            for c in range(ox.shape[0]):
                cnt[out[t, 1] + oy[c], out[t, 0] + ox[c]] += 1
        m += extra
        runs[where, 1] += extra
        for r in range(runs.shape[0]):
            if runs[r, 0] > i:
                runs[r, 0] += extra
                runs[r, 1] += extra
    return out[:m].copy()


@njit(cache=True)
def _runs_in_box(P, x0, y0, x1, y1, margin):
    """Index ranges `[a, b]` of the walk that pass through the box, widened by `margin`."""
    n = P.shape[0]
    out = np.empty((n // 2 + 2, 2), dtype=np.int64)
    count = 0
    i = 0
    while i < n:
        if x0 <= P[i, 0] <= x1 and y0 <= P[i, 1] <= y1:
            a = i
            while i < n and x0 <= P[i, 0] <= x1 and y0 <= P[i, 1] <= y1:
                i += 1
            lo = max(a - margin, 0)
            hi = min(i - 1 + margin, n - 1)
            if count > 0 and lo <= out[count - 1, 1]:
                out[count - 1, 1] = hi
            else:
                out[count, 0] = lo
                out[count, 1] = hi
                count += 1
        else:
            i += 1
    return out[:count]


# -- driver -------------------------------------------------------------------


class Refiner:
    """Holds the counter for all tours; improves them one move type at a time."""

    def __init__(self, region_mask: np.ndarray, region_origin: Point,
                 offsets: list[Point], paths: list[list[Point]]) -> None:
        ox = np.array([o[0] for o in offsets], dtype=np.int64)
        oy = np.array([o[1] for o in offsets], dtype=np.int64)
        ext = int(max(np.abs(ox).max(), np.abs(oy).max()))
        self.pad = pad = 2 * ext + 2
        pts = np.concatenate([np.array(p, dtype=np.int64).reshape(-1, 2) for p in paths if p])
        rx0, ry0 = region_origin
        rh, rw = region_mask.shape
        x0 = min(rx0, int(pts[:, 0].min())) - pad
        y0 = min(ry0, int(pts[:, 1].min())) - pad
        x1 = max(rx0 + rw - 1, int(pts[:, 0].max())) + pad
        y1 = max(ry0 + rh - 1, int(pts[:, 1].max())) + pad
        self.origin = (x0, y0)
        self.reg = np.zeros((y1 - y0 + 1, x1 - x0 + 1), dtype=np.bool_)
        self.reg[ry0 - y0 : ry0 - y0 + rh, rx0 - x0 : rx0 - x0 + rw] = region_mask
        self.cnt = np.zeros(self.reg.shape, dtype=np.int32)
        self.ox, self.oy = ox, oy
        # The runs of every cutter row and column, for the segment test.
        cx0, cy0 = int(ox.min()), int(oy.min())
        rows = int(oy.max()) - cy0 + 1
        cols = int(ox.max()) - cx0 + 1
        shape = np.zeros((rows, cols), dtype=bool)
        shape[oy - cy0, ox - cx0] = True

        def runs_of(lines: np.ndarray, first: int) -> tuple[np.ndarray, np.ndarray]:
            found = []
            for line in lines:
                edges = np.diff(np.concatenate(([0], line.astype(np.int8), [0])))
                starts = np.flatnonzero(edges == 1) + first
                ends = np.flatnonzero(edges == -1) - 1 + first
                found.append(list(zip(starts.tolist(), ends.tolist())))
            most = max(1, max(len(f) for f in found))
            table = np.zeros((len(found), most, 2), dtype=np.int64)
            count = np.zeros(len(found), dtype=np.int64)
            for i, f in enumerate(found):
                count[i] = len(f)
                for j, (lo, hi) in enumerate(f):
                    table[i, j] = (lo, hi)
            return table, count

        rrun, rcnt = runs_of(shape, cx0)
        crun, ccnt = runs_of(shape.T, cy0)
        # The reroute move is exact for every shape now; kept as a switch.
        self.convex = True
        self.spans = (rrun, rcnt, crun, ccnt, cy0, cx0)
        self.tours = [expand([(x - x0, y - y0) for x, y in p]) for p in paths]
        for P in self.tours:
            _stamp_all(self.cnt, P, ox, oy)

    def lengths(self) -> list[int]:
        return [len(P) if len(P) > 1 else 0 for P in self.tours]

    def uncovered(self) -> int:
        return int((self.reg & (self.cnt <= 0)).sum())

    def paths(self) -> list[list[Point]]:
        x0, y0 = self.origin
        return [[(x + x0, y + y0) for x, y in compress(P)] for P in self.tours]

    @staticmethod
    def _corners(P: np.ndarray) -> np.ndarray:
        d = np.diff(np.vstack([P[-1:], P, P[:1]]), axis=0)
        turn = np.any(d[1:] != d[:-1], axis=1)
        return np.flatnonzero(turn).astype(np.int64)

    def improve(self, t: int, rng: random.Random, window: int = 64,
                max_segments: int = 4, qmax: int = 4096, ties: int = 0) -> int:
        """One round of both moves on tour t, from a random rotation."""
        P = self.tours[t]
        if len(P) < 4:
            return 0
        P = np.roll(P, -rng.randrange(len(P)), axis=0)
        P, g1 = _shortcut_pass(P, self.cnt, self.reg, self.ox, self.oy, window)
        g2 = 0
        if self.convex and len(P) >= 4:
            P = np.roll(P, -rng.randrange(len(P)), axis=0)
            corners = self._corners(P)
            P, g2 = _reroute_pass(P, self.cnt, self.reg, self.ox, self.oy, *self.spans,
                                  corners, max_segments, qmax, self.pad // 2, ties)
        self.tours[t] = P
        return g1 + g2

    def _local(self, box, window: int, max_segments: int, qmax: int) -> None:
        """Shortcut and reroute on the parts of all tours that pass through `box`."""
        x0, y0, x1, y1 = box
        for t, P in enumerate(self.tours):
            if len(P) < 8:
                continue
            runs = _runs_in_box(P, x0, y0, x1, y1, 4)
            # From the back, so that earlier indices stay valid.
            for a, b in runs[::-1]:
                a, b = int(a), int(b)
                if b - a < 3:
                    continue
                part = np.ascontiguousarray(P[a : b + 1])
                part, _ = _shortcut_pass(part, self.cnt, self.reg, self.ox, self.oy, window)
                if len(part) >= 4:
                    steps = np.diff(part, axis=0)
                    turn = np.flatnonzero(np.any(steps[1:] != steps[:-1], axis=1)) + 1
                    corners = np.concatenate(([0], turn, [len(part) - 1])).astype(np.int64)
                    part, _ = _reroute_pass(part, self.cnt, self.reg, self.ox, self.oy,
                                            *self.spans, corners, max_segments, qmax,
                                            self.pad // 2, 0)
                P = np.concatenate([P[:a], part, P[b + 1 :]])
            self.tours[t] = P

    def _recount(self) -> None:
        self.cnt[:] = 0
        for P in self.tours:
            _stamp_all(self.cnt, P, self.ox, self.oy)

    def lns(self, deadline: float, rng: random.Random, size: int | None = None,
            lams=(0.3, 1.0, 2.5)) -> tuple[int, int]:
        """Inject the anchors of a low-spill cover of a window, refine there, keep gains.

        The window is drawn on the longest tour. Its region cells get a fresh
        greedy cover (`anchors._cover`); the tour that passes nearest visits
        each new anchor by a walk out and back; then shortcut and reroute run
        on every piece of tour in the window. The step is kept if the longest
        tour got shorter, or stayed and the total got shorter. Coverage holds
        throughout: the injection only adds points, and the moves keep every
        cell swept. Returns `(steps, kept)`.

        A rejected step restores the counter in a box around the window. As
        a guard against a change outside that box, the counter is rebuilt
        from the tours at the end, and the whole call is undone if a cell
        came out unswept.
        """
        from .anchors import _cover

        shape = np.zeros((int(self.oy.max() - self.oy.min()) + 1,
                          int(self.ox.max() - self.ox.min()) + 1), dtype=np.bool_)
        shape[self.oy - self.oy.min(), self.ox - self.ox.min()] = True
        cx0, cy0 = int(self.ox.min()), int(self.oy.min())
        border = max(shape.shape)
        fixed = size
        steps = kept = 0
        entry = [Q for Q in self.tours]
        H, W = self.reg.shape
        while time.perf_counter() < deadline:
            # Windows of 2 to 6 cutter widths: small ones are fast, large ones
            # can move a whole lane.
            size = fixed or rng.choice((2, 3, 4, 6)) * border
            lengths = self.lengths()
            t = max(range(len(lengths)), key=lengths.__getitem__)
            P = self.tours[t]
            if len(P) < 8:
                break
            px, py = P[rng.randrange(len(P))]
            wx0 = max(int(px) - rng.randrange(size), 0)
            wy0 = max(int(py) - rng.randrange(size), 0)
            sub = self.reg[wy0 : wy0 + size, wx0 : wx0 + size]
            if not sub.any():
                continue
            # The greedy cover scans in raster order; scanning a mirrored or
            # transposed window gives a different cover of the same cells.
            padded, stamp = np.pad(sub, border), shape
            swap, flip_y, flip_x = rng.random() < 0.5, rng.random() < 0.5, rng.random() < 0.5
            if swap:
                padded, stamp = padded.T, stamp.T
            if flip_y:
                padded, stamp = padded[::-1], stamp[::-1]
            if flip_x:
                padded, stamp = padded[:, ::-1], stamp[:, ::-1]
            corners = _cover(np.ascontiguousarray(padded), np.ascontiguousarray(stamp),
                             rng.choice(lams))
            cy, cx = corners[:, 0], corners[:, 1]
            if flip_x:
                cx = padded.shape[1] - stamp.shape[1] - cx
            if flip_y:
                cy = padded.shape[0] - stamp.shape[0] - cy
            if swap:
                cy, cx = cx, cy
            pts = np.empty((len(corners), 2), dtype=np.int64)
            pts[:, 0] = cx - border + wx0 - cx0
            pts[:, 1] = cy - border + wy0 - cy0
            box = (wx0 - 2 * border, wy0 - 2 * border,
                   wx0 + size + 2 * border, wy0 + size + 2 * border)
            # Everything a step can touch lies well inside this patch.
            reach = 6 * border + 16
            patch = (slice(max(wy0 - reach, 0), min(wy0 + size + reach, H)),
                     slice(max(wx0 - reach, 0), min(wx0 + size + reach, W)))
            saved = ([Q for Q in self.tours], self.cnt[patch].copy())
            before = (max(lengths), sum(lengths))
            # Each anchor joins the tour that passes nearest.
            runs = [_runs_in_box(Q, *box, 0) if len(Q) > 1 else np.zeros((0, 2), dtype=np.int64)
                    for Q in self.tours]
            near = np.full((len(self.tours), len(pts)), 1 << 40, dtype=np.int64)
            for u, Q in enumerate(self.tours):
                if len(runs[u]):
                    _nearest(Q, runs[u], pts, near[u])
            owner = near.argmin(axis=0)
            for u in range(len(self.tours)):
                mine = pts[owner == u]
                if len(mine) and len(runs[u]):
                    self.tours[u] = _inject(self.tours[u], runs[u], mine, self.cnt,
                                            self.ox, self.oy)
            for _ in range(3):
                self._local(box, 64, 4, 4096)
            now = self.lengths()
            steps += 1
            if (max(now), sum(now)) < before:
                kept += 1
            elif (max(now), sum(now)) > before:
                self.tours = saved[0]
                self.cnt[patch] = saved[1]
        self._recount()
        if self.uncovered():
            self.tours = entry
            self._recount()
            return steps, 0
        return steps, kept

    def balance(self) -> bool:
        """Trade work from a longer tour to a shorter one.

        Two moves: hand over one part, or swap a part for a part of the other
        tour. Neither can uncover a cell. A move is taken when the longer of
        the two tours gets shorter; the longest tour is tried first, then the
        next (work may have to pass through a tour in the middle).
        """
        lengths = self.lengths()
        reach = max(2, int(max(np.abs(self.ox).max(), np.abs(self.oy).max())))
        for a in sorted(range(len(lengths)), key=lambda t: -lengths[t]):
            A = self.tours[a]
            if len(A) < 16:
                continue
            best = None
            for b in range(len(self.tours)):
                B = self.tours[b]
                if b == a or len(B) < 8 or lengths[a] - lengths[b] < 8:
                    continue
                stride = max(1, len(A) // 4000)
                peak, i, j, ib = _find_transfer(A, B, lengths[a], lengths[b], reach, stride)
                if peak >= 0 and (best is None or peak < best[0]):
                    best = (int(peak), "give", b, (int(i), int(j), int(ib)))
                peak, i, j, p, q, rev = _find_exchange(A, B, lengths[a], lengths[b], reach, 2500)
                if peak >= 0 and (best is None or peak < best[0]):
                    best = (int(peak), "swap", b, (int(i), int(j), int(p), int(q), int(rev)))
            if best is None:
                continue
            _, kind, b, move = best
            apply = _apply_transfer if kind == "give" else _apply_exchange
            self.tours[a], self.tours[b] = apply(
                A, self.tours[b], *move, self.cnt, self.ox, self.oy
            )
            return True
        return False

    def _trade(self, deadline: float, rng: random.Random, max_segments: int) -> None:
        """Balance the tours as long as the longest one gets shorter."""
        if len(self.tours) < 2:
            return
        start = max(self.lengths())
        saved = ([P.copy() for P in self.tours], self.cnt.copy())
        for _ in range(300):
            if time.perf_counter() >= deadline or not self.balance():
                break
            self.descend(deadline, rng, max_segments, drift=False)
        if max(self.lengths()) >= start:
            self.tours, self.cnt = saved

    def run(self, deadline: float, rng: random.Random, max_segments: int = 4,
            drift: bool = False) -> None:
        """Descend and balance; with `drift`, search on until the deadline.

        The long phase alternates the large neighbourhood search (`lns`), a
        short drift, and the trades between tours. Every step keeps the
        region covered and none makes the longest tour longer.
        """
        self.descend(deadline, rng, max_segments, drift=False)
        self._trade(deadline, rng, max_segments)
        if not drift:
            return
        _seed_kernel(rng.randrange(1 << 30))
        while (now := time.perf_counter()) < deadline:
            left = deadline - now
            self.lns(now + max(0.5, 0.2 * left), rng)
            self.descend(min(deadline, time.perf_counter() + max(0.2, 0.03 * left)),
                         rng, max_segments, drift=True)
            self._trade(deadline, rng, max_segments)

    def descend(self, deadline: float, rng: random.Random, max_segments: int = 4,
                drift: bool = False) -> None:
        """Descend until no move gains; with `drift`, go on until the deadline.

        The drift phase also takes reroutes that gain nothing, at random. No
        move ever makes a tour longer, so the tours only improve.
        """
        idle = [0] * len(self.tours)
        while time.perf_counter() < deadline:
            order = sorted(range(len(self.tours)), key=lambda t: -len(self.tours[t]))
            progress = False
            for t in order:
                if idle[t] >= 3 or time.perf_counter() >= deadline:
                    continue
                gain = self.improve(t, rng, max_segments=max_segments)
                idle[t] = 0 if gain > 0 else idle[t] + 1
                progress = progress or idle[t] < 3
            if not progress:
                break
        if not drift or not self.convex:
            return
        _seed_kernel(rng.randrange(1 << 30))
        while time.perf_counter() < deadline:
            for t in sorted(range(len(self.tours)), key=lambda t: -len(self.tours[t])):
                if time.perf_counter() >= deadline:
                    break
                self.improve(t, rng, max_segments=max_segments, ties=1)
