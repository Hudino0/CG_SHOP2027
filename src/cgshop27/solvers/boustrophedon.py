"""A baseline solver: split the region into horizontal bands and mow them.

The construction is deliberately simple but feasible by construction, which
makes it a useful reference point and a way to exercise the whole pipeline.

Why it covers everything: let `[r0, r1]` be the longest run of consecutive rows
the cutter occupies (relative to its center) and `[cxmin, cxmax]` its column
range. Sweeping the center horizontally along `y = a - r0` covers every region
row in `[a, a + (r1 - r0)]`, because each of those rows sits at an offset the
cutter occupies. Sweeping the center over `x` in `[colmin - cxmax, colmax -
cxmin]` then covers every column in `[colmin, colmax]` for each of those rows,
whichever column of the cutter happens to do the covering.

Tours may leave the region freely, so no band ever has to dodge a hole.
"""

from __future__ import annotations

import numpy as np
from cgshop2027_pyutils.grid import CellSet
from cgshop2027_pyutils.schemas import CGSHOP2027Instance, CGSHOP2027Solution

from ..catalog import cutter_cells, region_cells
from ._tour import Point, make_tour

Band = tuple[int, int, int]  # (center_y, x_start, x_end)


def _longest_row_run(cutter: CellSet) -> tuple[int, int]:
    """The longest run of consecutive occupied rows, in cutter-relative coords."""
    occupied = cutter.mask.any(axis=1)
    best = (0, 0)
    run_start = None
    for index, filled in enumerate([*occupied, False]):
        if filled and run_start is None:
            run_start = index
        elif not filled and run_start is not None:
            if index - run_start > best[1] - best[0] + 1 or best == (0, 0):
                best = (run_start, index - 1)
            run_start = None
    offset = cutter.origin[1]
    return best[0] + offset, best[1] + offset


def _bands(region: CellSet, cutter: CellSet) -> list[Band]:
    """One sweep line per band of rows, clipped to the columns that need it."""
    row_lo, row_hi = _longest_row_run(cutter)
    band_height = row_hi - row_lo + 1
    col_lo, col_hi = cutter.bounds[0], cutter.bounds[2]

    mask = region.mask
    origin_x, origin_y = region.origin
    bands: list[Band] = []
    for top in range(0, mask.shape[0], band_height):
        strip = mask[top : top + band_height]
        columns = np.nonzero(strip.any(axis=0))[0]
        if columns.size == 0:
            continue  # nothing to mow in this band
        first, last = int(columns[0]) + origin_x, int(columns[-1]) + origin_x
        bands.append((top + origin_y - row_lo, first - col_hi, last - col_lo))
    return bands


def _group_cost(bands: list[Band]) -> int:
    """Rough length of the closed serpentine over `bands`: across and back up."""
    if not bands:
        return 0
    horizontal = sum(end - start for _, start, end in bands)
    vertical = 2 * (bands[-1][0] - bands[0][0])
    return horizontal + vertical


def _split(bands: list[Band], k: int) -> list[list[Band]]:
    """Cut the band list into at most `k` contiguous groups, balancing cost.

    Group cost grows as a group is extended, so the usual greedy-under-a-limit
    test is exact and a binary search finds the best achievable maximum.
    """
    if k <= 1 or len(bands) <= 1:
        return [bands]

    def groups_for(limit: int) -> list[list[Band]] | None:
        groups: list[list[Band]] = []
        current: list[Band] = []
        for band in bands:
            if current and _group_cost([*current, band]) > limit:
                groups.append(current)
                current = []
                if len(groups) == k:
                    return None
            current.append(band)
        groups.append(current)
        return groups if len(groups) <= k else None

    low = max(_group_cost([band]) for band in bands)
    high = _group_cost(bands)
    best = groups_for(high) or [bands]
    while low <= high:
        middle = (low + high) // 2
        found = groups_for(middle)
        if found is None:
            low = middle + 1
        else:
            best, high = found, middle - 1
    return best


def _serpentine(bands: list[Band]) -> list[Point]:
    """Waypoints alternating direction band by band, so turns stay cheap."""
    waypoints: list[Point] = []
    for index, (y, x_start, x_end) in enumerate(bands):
        left, right = (x_start, x_end) if index % 2 == 0 else (x_end, x_start)
        waypoints.append((left, y))
        waypoints.append((right, y))
    return waypoints


def solve(instance: CGSHOP2027Instance) -> CGSHOP2027Solution:
    """Mow the region in horizontal bands, shared out among the cutters."""
    region = region_cells(instance)
    cutter = cutter_cells(instance)
    bands = _bands(region, cutter)
    k = instance.number_of_cutters

    if not bands:  # an empty region: park every cutter and travel nowhere
        parked = [make_tour([(0, 0)]) for _ in range(k)]
        return CGSHOP2027Solution(instance_uid=instance.instance_uid, tours=parked)

    groups = _split(bands, k)
    tours = [make_tour(_serpentine(group)) for group in groups if group]

    # Spare cutters stand still at a corner: valid, and length zero.
    idle = (bands[0][1], bands[0][0])
    tours.extend(make_tour([idle]) for _ in range(k - len(tours)))

    return CGSHOP2027Solution(
        instance_uid=instance.instance_uid,
        tours=tours,
        meta={
            "algorithm": "boustrophedon",
            "bands": len(bands),
            "band_groups": [len(group) for group in groups],
        },
    )
