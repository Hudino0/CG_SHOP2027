"""Loading instances and describing them.

The catalog is the "process" half of the pipeline: it turns the raw JSON files
into one flat table with the numbers that actually drive algorithm choices --
how big the region is, how big the cutter is, how many cutters there are, and
what that implies for a lower bound on the objective.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from cgshop2027_pyutils.grid import CellSet, rasterize, rasterize_ring
from cgshop2027_pyutils.io import read_instance
from cgshop2027_pyutils.schemas import CGSHOP2027Instance

from .config import INSTANCE_SUFFIX, INSTANCES

_FAMILY = re.compile(r"^[a-zA-Z]+")


def instance_paths(root: Path | None = None) -> list[Path]:
    """Every `*.instance.json` under `root`, sorted by name."""
    root = INSTANCES if root is None else root
    return sorted(root.rglob(f"*{INSTANCE_SUFFIX}"))


def load(path: Path) -> CGSHOP2027Instance:
    return read_instance(path)


def iter_instances(root: Path | None = None) -> Iterator[tuple[Path, CGSHOP2027Instance]]:
    for path in instance_paths(root):
        yield path, load(path)


def find_instance(name: str, root: Path | None = None) -> Path:
    """Resolve an instance by uid, file name or path."""
    candidate = Path(name)
    if candidate.is_file():
        return candidate
    stem = candidate.name.removesuffix(INSTANCE_SUFFIX).removesuffix(".json")
    for path in instance_paths(root):
        if path.name.removesuffix(INSTANCE_SUFFIX) == stem:
            return path
    raise FileNotFoundError(f"No instance matching {name!r} under {root or INSTANCES}")


# -- geometry helpers ------------------------------------------------------


def region_cells(instance: CGSHOP2027Instance) -> CellSet:
    return rasterize(instance.region_to_cover)


def cutter_cells(instance: CGSHOP2027Instance) -> CellSet:
    """The cutter footprint expressed relative to its center, as the verifier sees it."""
    cx, cy = instance.cutter_center
    return rasterize_ring(instance.cutter).translated(-cx, -cy)


def count_components(cells: CellSet) -> int:
    """Number of 4-connected components, via an iterative flood fill."""
    mask = cells.mask
    seen = np.zeros_like(mask)
    total = 0
    height, width = mask.shape
    for start in zip(*np.nonzero(mask & ~seen)):
        if seen[start]:
            continue
        total += 1
        stack = [start]
        seen[start] = True
        while stack:
            row, col = stack.pop()
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                r, c = row + dr, col + dc
                if 0 <= r < height and 0 <= c < width and mask[r, c] and not seen[r, c]:
                    seen[r, c] = True
                    stack.append((r, c))
    return total


def max_cross_section(cutter: CellSet) -> int:
    """The widest row or column of the cutter.

    One unit of travel sweeps at most this many new cells, which is what makes
    the area lower bound below valid.
    """
    mask = cutter.mask
    return int(max(mask.sum(axis=0).max(), mask.sum(axis=1).max()))


def area_lower_bound(area: int, cutter_area: int, cross: int, k: int) -> int:
    """A lower bound on the longest tour.

    Each of the `k` cutters sweeps at most `cutter_area + length * cross` cells,
    so `area <= k * (cutter_area + L * cross)` for the longest tour `L`.
    """
    if cross <= 0:
        return 0
    return max(0, -(-(area - k * cutter_area) // (k * cross)))


# -- the catalog record ----------------------------------------------------


@dataclass(frozen=True)
class InstanceStats:
    instance_uid: str
    family: str
    path: str
    number_of_cutters: int
    region_area: int
    region_components: int
    region_width: int
    region_height: int
    bbox_fill: float
    outer_vertices: int
    holes: int
    hole_vertices: int
    cutter_area: int
    cutter_width: int
    cutter_height: int
    cutter_vertices: int
    cutter_center: tuple[int, int]
    cutter_cross_section: int
    area_over_cutter: float
    lower_bound: int

    def as_row(self) -> dict:
        return asdict(self)


def describe(path: Path, instance: CGSHOP2027Instance | None = None) -> InstanceStats:
    instance = instance if instance is not None else load(path)
    region = region_cells(instance)
    cutter = cutter_cells(instance)

    rx0, ry0, rx1, ry1 = region.bounds
    cx0, cy0, cx1, cy1 = cutter.bounds
    area = len(region)
    cutter_area = len(cutter)
    width, height = rx1 - rx0 + 1, ry1 - ry0 + 1
    cross = max_cross_section(cutter)
    k = instance.number_of_cutters
    holes = instance.region_to_cover.inner_boundaries

    return InstanceStats(
        instance_uid=instance.instance_uid,
        family=(_FAMILY.match(instance.instance_uid) or _FAMILY.match("x")).group(0),
        path=str(path),
        number_of_cutters=k,
        region_area=area,
        region_components=count_components(region),
        region_width=width,
        region_height=height,
        bbox_fill=round(area / (width * height), 4),
        outer_vertices=len(instance.region_to_cover.outer_boundary.x),
        holes=len(holes),
        hole_vertices=sum(len(h.x) for h in holes),
        cutter_area=cutter_area,
        cutter_width=cx1 - cx0 + 1,
        cutter_height=cy1 - cy0 + 1,
        cutter_vertices=len(instance.cutter.x),
        cutter_center=tuple(instance.cutter_center),
        cutter_cross_section=cross,
        area_over_cutter=round(area / cutter_area, 2) if cutter_area else 0.0,
        lower_bound=area_lower_bound(area, cutter_area, cross, k),
    )
