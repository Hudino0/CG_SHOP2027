"""Weighted area bound: a lower bound certified by a weight on the region cells.

Write `R` for the region, `C` for the cutter cells relative to the center and
`D_d = (C + d) \\ C` for the cells that a unit step in direction `d` adds
(`d` is one of the four unit vectors).

**Theorem (weighted area bound).** Let `u >= 0` be a weight on the cells of
`R` (zero elsewhere) with

    u(p + D_d) <= 1     for every lattice point p and every direction d,

and let `M = max_p u(p + C)`. Then in every solution with `k` tours the
longest tour has length `L >= (u(R) - k M) / k + 1` (when the bound is above
1).

*Proof.* A closed tour of length `L >= 1` visits lattice points `p_0, ...,
p_{L-1}` and returns to `p_0`. The cells it sweeps lie in `(p_0 + C)` and in
the sets `(p_i + C) \\ (p_{i-1} + C) = p_{i-1} + D_d`, `i = 1 .. L-1`. So the
weight it sweeps is at most `M + (L - 1)`. The `k` tours sweep all of `R`,
so `u(R) <= k (M + L - 1)`. ∎

`u = 1 / cross(C)` on every cell is feasible and gives the plain area bound.
The best `u` is the optimum of a linear program (a packing LP): maximize
`u(R)` under the constraints above. It is much larger than `|R| / cross(C)`
when the region has features thinner than the cutter: there a step sweeps
few region cells, and those cells can carry more weight.

**Lemma (pitch).** Let the instance be the coarse instance `(R', C')` scaled
by `g` (every contest instance is: `solvers.scale`). If `u'` is feasible for
`(R', C')`, then `u = u' / g` on each fine cell of a coarse cell is feasible
for `(R, C)`, with `u(R) = g u'(R')` and `M <= g M'`.

*Proof.* A fine step in x from `p = g P + t`, `0 <= t_x, t_y < g`, adds one
fine column next to each row end of `C`. These columns lie in the coarse
columns of the coarse step from `P`, and each of them splits between two
coarse rows: `g - t_y` fine cells in row `J` and `t_y` in row `J + 1`. So
`u(p + D_d) = ((g - t_y) u'(P + D'_d) + t_y u'(P + (0,1) + D'_d)) / g <= 1`.
The same holds for a step in y. A fine stamp is, in the same way, a convex
combination of four coarse stamps times `g`. ∎

So the program is solved on the coarse lattice, and the bound is
`g (u'(R') - k M') / k + 1`, rounded up to an even number (parity).

**Monotonicity.** The cutter used here is the orthoconvex hull of `C`: a
solution for `C` is a solution for the hull, and the hull has fewer added
cells per step.

Any feasible `u` is a certificate, whether optimal or not. So a first-order
method is enough: its iterate is divided by its largest row sum, which makes
it feasible, and the dual iterate bounds what the optimum could add.
"""

from __future__ import annotations

import math
import time

import numpy as np
from scipy import sparse

from .catalog import cutter_cells, orthoconvex_hull, region_cells
from .solvers.scale import coarsen, lattice_pitch

DIRECTIONS = ((0, 1), (0, -1), (1, 0), (-1, 0))  # (dy, dx)


def increments(cutter: np.ndarray) -> list[np.ndarray]:
    """The distinct sets `D_d` up to translation, as offsets `(dy, dx) >= 0`."""
    pad = np.pad(cutter.astype(bool), 1)
    found: dict[bytes, np.ndarray] = {}
    for dy, dx in DIRECTIONS:
        added = np.roll(pad, (dy, dx), axis=(0, 1)) & ~pad
        cells = np.argwhere(added)
        cells -= cells.min(axis=0)
        found.setdefault(cells.tobytes(), cells)
    return list(found.values())


def constraints(region: np.ndarray, sets: list[np.ndarray]) -> tuple[sparse.csr_matrix, np.ndarray]:
    """One row per translate of a set that holds two region cells or more."""
    H, W = region.shape
    index = -np.ones((H, W), dtype=np.int64)
    index[region] = np.arange(int(region.sum()))
    blocks = []
    for cells in sets:
        hy, hx = cells.max(axis=0)
        padded = np.pad(index, ((hy, hy), (hx, hx)), constant_values=-1)
        ph, pw = H + hy, W + hx  # positions of the set's corner
        rows, cols = [], []
        for dy, dx in cells:
            view = padded[dy : dy + ph, dx : dx + pw]
            where = np.flatnonzero(view >= 0)
            rows.append(where)
            cols.append(view.ravel()[where])
        rows, cols = np.concatenate(rows), np.concatenate(cols)
        block = sparse.csr_matrix((np.ones(len(rows), dtype=np.float64), (rows, cols)),
                                  shape=(ph * pw, int(region.sum())))
        blocks.append(block[np.diff(block.indptr) >= 2])
    return sparse.vstack(blocks, format="csr"), index


def weights(region: np.ndarray, cutter: np.ndarray, iterations: int = 6000,
            tolerance: float = 2e-3, deadline: float = math.inf) -> tuple[np.ndarray, float]:
    """A feasible weight on the region cells, and an upper bound on the optimum.

    Primal-dual hybrid gradient (Chambolle and Pock) on the packing program
    `max 1.u, A u <= 1, 0 <= u <= 1`. The iterate is not feasible, so each
    candidate is divided by its largest row sum; the best candidate wins. The
    dual iterate `y >= 0` gives `y.1 + sum(max(0, 1 - A'y))`, an upper bound
    on the optimum (weak duality), which tells when to stop.

    The weight is returned as a 2-D array, zero off the region.
    """
    A, _ = constraints(region, increments(cutter))
    m, n = A.shape
    start = np.full(n, 1.0 / max_cross_section_mask(cutter))
    best, value, upper = start, float(start.sum()), float(n)
    if m:
        At = A.T.tocsr()
        step = 0.95 / math.sqrt(float(np.diff(A.indptr).max()) * float(np.diff(At.indptr).max()))
        x, y, mean = start.copy(), np.zeros(m), np.zeros(n)
        for it in range(1, iterations + 1):
            moved = np.clip(x + step * (1.0 - At @ y), 0.0, 1.0)
            y = np.maximum(0.0, y + step * (A @ (2.0 * moved - x) - 1.0))
            x = moved
            mean += x
            if it % 250 == 0 or it == iterations:
                for candidate in (x, mean / it):
                    scaled = candidate / max(1.0, float((A @ candidate).max()))
                    if scaled.sum() > value:
                        best, value = scaled, float(scaled.sum())
                upper = min(upper, float(y.sum() + np.maximum(0.0, 1.0 - At @ y).sum()))
                if value >= (1.0 - tolerance) * upper or time.perf_counter() > deadline:
                    break
        # Guard against rounding: no row may be above 1.
        best = best / (max(1.0, float((A @ best).max())) * (1.0 + 1e-9))
    out = np.zeros(region.shape)
    out[region] = np.minimum(best, 1.0)
    return out, upper


def max_cross_section_mask(mask: np.ndarray) -> int:
    pad = np.pad(mask.astype(bool), 1)
    return max(int((pad[:, 1:] & ~pad[:, :-1]).sum()), int((pad[1:, :] & ~pad[:-1, :]).sum()))


def stamp_max(u: np.ndarray, cutter: np.ndarray) -> float:
    """`max_p u(p + C)`."""
    ch, cw = cutter.shape
    padded = np.pad(u, ((ch, ch), (cw, cw)))
    total = np.zeros((padded.shape[0] - ch + 1, padded.shape[1] - cw + 1))
    for dy, dx in np.argwhere(cutter):
        total += padded[dy : dy + total.shape[0], dx : dx + total.shape[1]]
    return float(total.max())


def weighted_bound(instance, iterations: int = 6000, time_limit: float = math.inf) -> dict:
    """The weighted area bound of an instance, with the numbers behind it.

    `lp_upper` is what the bound would be with the optimal weight: it shows
    how much the first-order solver left on the table.
    """
    began = time.perf_counter()
    g = lattice_pitch(instance)
    coarse, _ = coarsen(instance, g)
    k = instance.number_of_cutters
    region = region_cells(coarse).mask.astype(bool)
    hull = orthoconvex_hull(cutter_cells(coarse)).mask.astype(bool)
    u, upper = weights(region, hull, iterations, deadline=began + time_limit)
    total, peak = float(u.sum()), stamp_max(u, hull)

    def bound(weight: float) -> int:
        value = max(0, math.ceil(g * (weight - k * peak) / k + 1 - 1e-6))
        return value + value % 2

    cross = max_cross_section_mask(hull)
    return {
        "instance_uid": instance.instance_uid,
        "weighted_bound": bound(total),
        "lp_upper": bound(upper),
        "weight": round(g * total, 3),
        "stamp": round(g * peak, 3),
        "uniform_weight": round(g * int(region.sum()) / cross, 3),
        "cells": int(region.sum()),
        "seconds": round(time.perf_counter() - began, 1),
    }
