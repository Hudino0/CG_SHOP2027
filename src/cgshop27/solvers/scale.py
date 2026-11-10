"""Solve on a coarser lattice, then lift the tours back.

Two facts make this safe. Write `R` for the region, `C` for the cutter cells
relative to the center, and `f * X + t` for the cells `[f*i + t_x, f*i + t_x +
f) x [f*j + t_y, f*j + t_y + f)` over the coarse cells `(i, j)` of `X`.

**Lemma (lifting).** Let `R' , C'` be sets of coarse cells with

    R  ⊆  f * R' + o          (the coarse region contains the region)
    f * C' + p  ⊆  C          (the coarse cutter fits inside the cutter)

If coarse tours visit the lattice points `A'` and `R' ⊆ A' ⊕ C'`, then the
tours `P -> f * P + (o - p)` cover `R`.

*Proof.* Take a cell of `R`. It lies in the block of some coarse cell `q` of
`R'`, and `q = a + c` with `a` in `A'` and `c` in `C'`. The block of `q` is
`f * a + o + f * c + [0, f)^2`, which is `(f * a + o - p) + (f * c + p + [0,
f)^2)`. The first part is a lifted tour point and the second part lies in `C`.
A lifted tour passes through every lifted point: an axis-parallel edge maps to
an axis-parallel edge that contains the images of its lattice points. ∎

**Exact case.** Every contest instance has all region and cutter coordinates
on a lattice of pitch `g` (1, 2 or 6). With `f = g` both inclusions are
equalities, so nothing is lost by construction: the coarse instance is the
instance the organizers scaled up. Only finer lanes (not multiples of `g`)
are out of reach; the lattice refiner can find those afterwards.

A further factor (`extra`) keeps the cutter at most `max_width` coarse cells
wide. Then the inclusions are proper: the region is rounded out and the
cutter is rounded in, and the phase `p` is the one that keeps the most cutter.
"""

from __future__ import annotations

import inspect
import math
from functools import reduce

import numpy as np
from cgshop2027_pyutils.grid import CellSet
from cgshop2027_pyutils.schemas import CGSHOP2027Instance, CGSHOP2027Solution, CutterTour

from ..catalog import MaskInstance, cutter_cells, region_cells

Point = tuple[int, int]


def lattice_pitch(instance: CGSHOP2027Instance) -> int:
    """The largest `g` with every region and cutter coordinate on a `g`-lattice."""
    region = instance.region_to_cover
    rings = [region.outer_boundary, *region.inner_boundaries]
    x0, y0 = rings[0].x[0], rings[0].y[0]
    cx, cy = instance.cutter_center
    deltas = [x - x0 for ring in rings for x in ring.x]
    deltas += [y - y0 for ring in rings for y in ring.y]
    deltas += [x - cx for x in instance.cutter.x]
    deltas += [y - cy for y in instance.cutter.y]
    return max(1, reduce(math.gcd, deltas, 0))


def coarse_region(region: CellSet, f: int) -> tuple[CellSet, Point]:
    """The coarse cells whose block meets the region, and the offset `o`."""
    if f == 1:
        return CellSet(region.mask, (0, 0)), region.origin
    height, width = region.mask.shape
    rows, cols = -(-height // f), -(-width // f)
    padded = np.zeros((rows * f, cols * f), dtype=bool)
    padded[:height, :width] = region.mask
    mask = padded.reshape(rows, f, cols, f).any(axis=(1, 3))
    return CellSet(mask, (0, 0)), region.origin


def coarse_cutter(cutter: CellSet, f: int) -> tuple[CellSet, Point]:
    """The coarse cells whose block lies inside the cutter, and the phase `p`.

    The phase with the most coarse cells wins; ties go to the smallest phase.
    """
    if f == 1:
        return cutter, (0, 0)
    x0, y0 = cutter.origin
    height, width = cutter.mask.shape
    best = None
    for py in range(f):
        for px in range(f):
            # Coarse cell (i, j) holds the cells f*i + px .. f*i + px + f - 1.
            i0 = -(-(x0 - px) // f)
            j0 = -(-(y0 - py) // f)
            cols = (x0 + width - px) // f - i0
            rows = (y0 + height - py) // f - j0
            if rows <= 0 or cols <= 0:
                continue
            left, bottom = f * i0 + px - x0, f * j0 + py - y0
            part = cutter.mask[bottom : bottom + rows * f, left : left + cols * f]
            mask = part.reshape(rows, f, cols, f).all(axis=(1, 3))
            if best is None or mask.sum() > best[0]:
                best = (int(mask.sum()), mask, (i0, j0), (px, py))
    if best is None or best[0] == 0:
        raise ValueError(f"the cutter holds no {f} x {f} block")
    _, mask, origin, phase = best
    rows = np.flatnonzero(mask.any(axis=1))
    cols = np.flatnonzero(mask.any(axis=0))
    mask = mask[rows[0] : rows[-1] + 1, cols[0] : cols[-1] + 1]
    return CellSet(mask, (origin[0] + int(cols[0]), origin[1] + int(rows[0]))), phase


def coarsen(instance, f: int) -> tuple[MaskInstance, Point]:
    """The instance on a lattice `f` times coarser, and the lift offset `o - p`."""
    region, offset = coarse_region(region_cells(instance), f)
    cutter, phase = coarse_cutter(cutter_cells(instance), f)
    coarse = MaskInstance(instance.instance_uid, instance.number_of_cutters, region, cutter)
    return coarse, (offset[0] - phase[0], offset[1] - phase[1])


def lift(solution: CGSHOP2027Solution, f: int, shift: Point, meta: dict) -> CGSHOP2027Solution:
    tours = [
        CutterTour(x=[f * x + shift[0] for x in tour.x], y=[f * y + shift[1] for y in tour.y])
        for tour in solution.tours
    ]
    return CGSHOP2027Solution(
        instance_uid=solution.instance_uid, tours=tours, meta={**solution.meta, **meta}
    )


def factor(instance: CGSHOP2027Instance, max_width: int | None) -> tuple[int, int]:
    """`(g, extra)`: the exact pitch and the further factor for wide cutters."""
    g = lattice_pitch(instance)
    cutter = cutter_cells(instance)
    width = min(cutter.width, cutter.height) // g
    extra = 1 if not max_width else -(-width // max_width)
    return g, extra


def scaled(solver, max_width: int | None = None):
    """Wrap `solver` so that it works on the coarse lattice of each instance."""

    def solve(instance: CGSHOP2027Instance, **options) -> CGSHOP2027Solution:
        g, extra = factor(instance, max_width)
        f = g * extra
        if f == 1:
            return solver(instance, **options)
        coarse, shift = coarsen(instance, f)
        solution = solver(coarse, **options)
        return lift(solution, f, shift, {"pitch": g, "coarsening": extra})

    # Keep the wrapped solver's options visible (the CLI looks for `time_limit`).
    solve.__signature__ = inspect.signature(solver)
    solve.__doc__ = solver.__doc__
    return solve
