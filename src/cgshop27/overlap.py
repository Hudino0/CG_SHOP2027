"""How much of the region two or more cutters sweep.

The verifier only asks whether the union of all sweeps covers the region. This
module looks at each tour on its own: which region cells it sweeps, and which
of them another tour sweeps too. Overlap is not always waste -- only the
longest tour counts for the score -- but it shows where the zones of the
cutters meet and where one cutter crosses the zone of another.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations

import numpy as np
from cgshop2027_pyutils.grid import CellSet, dilate
from cgshop2027_pyutils.schemas import CGSHOP2027Instance, CGSHOP2027Solution, CutterTour

from .catalog import cutter_cells, region_cells


@dataclass(frozen=True)
class Overlap:
    run: str
    instance_uid: str
    cutters: int
    region_area: int
    #: Percent of the region that two or more tours sweep.
    shared: float
    #: Percent of the region that both tours of a pair sweep, keyed "1-2".
    pairs: dict[str, float] = field(default_factory=dict)
    #: For each tour, the percent of its own region cells another tour sweeps.
    own: list[float] = field(default_factory=list)

    def as_row(self) -> dict:
        return {
            "run": self.run,
            "instance_uid": self.instance_uid,
            "cutters": self.cutters,
            "region_area": self.region_area,
            "shared": self.shared,
            "pairs": self.pairs,
            "own": self.own,
        }


def _anchors(tour: CutterTour) -> CellSet:
    """Every lattice point the tour stops on or passes over."""
    points = list(zip(tour.x, tour.y, strict=True))
    xs, ys = tour.x, tour.y
    x0, y0 = min(xs), min(ys)
    mask = np.zeros((max(ys) - y0 + 1, max(xs) - x0 + 1), dtype=bool)
    mask[points[0][1] - y0, points[0][0] - x0] = True
    for (ax, ay), (bx, by) in zip(points, [*points[1:], points[0]]):
        mask[min(ay, by) - y0 : max(ay, by) - y0 + 1, min(ax, bx) - x0 : max(ax, bx) - x0 + 1] = True
    return CellSet(mask, (x0, y0))


def swept_masks(instance: CGSHOP2027Instance, solution: CGSHOP2027Solution) -> tuple[np.ndarray, list[np.ndarray]]:
    """The region mask, and for each tour the region cells it sweeps."""
    region = region_cells(instance)
    cutter = cutter_cells(instance)
    masks = []
    for tour in solution.tours:
        swept = dilate(_anchors(tour), cutter)
        # `difference` aligns the result to the region's own grid.
        masks.append(region.mask & ~region.difference(swept).mask)
    return region.mask, masks


def measure(instance: CGSHOP2027Instance, solution: CGSHOP2027Solution, run: str) -> Overlap:
    region, masks = swept_masks(instance, solution)
    area = int(region.sum())
    count = np.sum(masks, axis=0) if masks else np.zeros_like(region, dtype=int)
    shared = count >= 2

    def percent(part: int, whole: int) -> float:
        return round(100 * part / whole, 2) if whole else 0.0

    return Overlap(
        run=run,
        instance_uid=instance.instance_uid,
        cutters=len(masks),
        region_area=area,
        shared=percent(int(shared.sum()), area),
        pairs={
            f"{i + 1}-{j + 1}": percent(int((masks[i] & masks[j]).sum()), area)
            for i, j in combinations(range(len(masks)), 2)
        },
        own=[percent(int((m & shared).sum()), int(m.sum())) for m in masks],
    )
