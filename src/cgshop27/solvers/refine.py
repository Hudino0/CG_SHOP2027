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
def _seg_covers(qx, qy, x0, y0, x1, y1, rlo, rhi, clo, chi, cy0, cx0):
    """Does the axis-parallel segment (x0,y0)-(x1,y1) sweep cell (qx, qy)?"""
    if y0 == y1:
        dy = qy - y0 - cy0
        if dy < 0 or dy >= rlo.shape[0] or rlo[dy] > rhi[dy]:
            return False
        lo = min(x0, x1)
        hi = max(x0, x1)
        # Need x in [lo, hi] with qx - x in [rlo, rhi].
        return qx - rhi[dy] <= hi and qx - rlo[dy] >= lo
    dx = qx - x0 - cx0
    if dx < 0 or dx >= clo.shape[0] or clo[dx] > chi[dx]:
        return False
    lo = min(y0, y1)
    hi = max(y0, y1)
    return qy - chi[dx] <= hi and qy - clo[dx] >= lo


@njit(cache=True)
def _walk_covers(qs, nq, wx, wy, nw, rlo, rhi, clo, chi, cy0, cx0):
    for q in range(nq):
        ok = False
        for s in range(nw - 1):
            if _seg_covers(qs[q, 0], qs[q, 1], wx[s], wy[s], wx[s + 1], wy[s + 1],
                           rlo, rhi, clo, chi, cy0, cx0):
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
               rlo, rhi, clo, chi, cy0, cx0, res):
    """Shortest walk a -> b with <= 3 corners, below `limit`, sweeping all qs.

    The walks are a, (ax, t), (u, t), (u, by), b (vertical first) and the mirror
    a, (t, ay), (t, u), (bx, u), b. `t` and `u` range over the box. Writes the
    five points into res and returns the length, or -1.
    """
    wx = np.empty(5, dtype=np.int64)
    wy = np.empty(5, dtype=np.int64)
    best = limit
    found = -1
    for mode in range(2):
        for t in range(by0 if mode == 0 else bx0, (by1 if mode == 0 else bx1) + 1):
            if mode == 0:
                base = abs(ay - t) + abs(t - by)
            else:
                base = abs(ax - t) + abs(t - bx)
            if base + (abs(ax - bx) if mode == 0 else abs(ay - by)) >= best:
                continue
            lo = bx0 if mode == 0 else by0
            hi = bx1 if mode == 0 else by1
            for u in range(lo, hi + 1):
                if mode == 0:
                    length = base + abs(u - ax) + abs(bx - u)
                else:
                    length = base + abs(u - ay) + abs(by - u)
                if length >= best:
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
                if _walk_covers(qs, nq, wx, wy, 5, rlo, rhi, clo, chi, cy0, cx0):
                    best = length
                    found = length
                    for s in range(5):
                        res[s, 0] = wx[s]
                        res[s, 1] = wy[s]
    return found


@njit(cache=True)
def _reroute_pass(P, cnt, reg, ox, oy, rlo, rhi, clo, chi, cy0, cx0,
                  corners, max_segments, qmax, pad):
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
                                    rlo, rhi, clo, chi, cy0, cx0, res)
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
        # Row and column spans of the cutter, for the segment test.
        cx0, cy0 = int(ox.min()), int(oy.min())
        rows = int(oy.max()) - cy0 + 1
        cols = int(ox.max()) - cx0 + 1
        rlo = np.full(rows, 1 << 30, dtype=np.int64)
        rhi = np.full(rows, -(1 << 30), dtype=np.int64)
        clo = np.full(cols, 1 << 30, dtype=np.int64)
        chi = np.full(cols, -(1 << 30), dtype=np.int64)
        for dx, dy in offsets:
            rlo[dy - cy0] = min(rlo[dy - cy0], dx)
            rhi[dy - cy0] = max(rhi[dy - cy0], dx)
            clo[dx - cx0] = min(clo[dx - cx0], dy)
            chi[dx - cx0] = max(chi[dx - cx0], dy)
        # Rows and columns must be intervals for the segment test to be exact.
        cells = set(offsets)
        self.convex = all((dx, dy) in cells for dx in range(int(rlo[dy - cy0]), int(rhi[dy - cy0]) + 1)
                          for dy in range(cy0, cy0 + rows)) and             all((dx, dy) in cells for dy in range(int(clo[dx - cx0]), int(chi[dx - cx0]) + 1)
                for dx in range(cx0, cx0 + cols))
        self.spans = (rlo, rhi, clo, chi, cy0, cx0)
        self.tours = [expand([(x - x0, y - y0) for x, y in p]) for p in paths]
        for P in self.tours:
            for x, y in P:
                self.cnt[y + oy, x + ox] += 1

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
                max_segments: int = 4, qmax: int = 4096) -> int:
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
                                  corners, max_segments, qmax, self.pad // 2)
        self.tours[t] = P
        return g1 + g2

    def run(self, deadline: float, rng: random.Random, max_segments: int = 4) -> None:
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
