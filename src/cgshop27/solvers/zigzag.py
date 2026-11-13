"""Lanes with a second orientation on the thin corridors that lie on cycles.

Take a corridor of length `X` and width `H` with `w < H < 2w` (`w` is the
cutter width across the corridor). There are two ways to mow it:

* two lanes along it: the cutter crosses every cross-section twice, cost `2X`;
* teeth across it (a zigzag): one crossing, cost `X H / w < 2X`.

The number of crossings of a cross-section, mod 2, is the same for all the
cross-sections of a corridor, and around a hole it is the winding number of
the tour mod 2. A move inside a window that does not hold the whole hole
cannot change it. So the local search never turns two lanes into a zigzag:
the constructor must choose.

A corridor that is a bridge of the region must be crossed an even number of
times (the tour is closed), so two lanes are right there. A corridor on a
cycle can be crossed once. This solver finds the thin corridors along the
lanes, keeps those that lie on a cycle of the corridor graph, gives them
lanes in the other orientation (the teeth), and routes all the lanes
together. Where the odd corridors do not form an Eulerian subgraph, the
routing pays the walk between them: that is the T-join of Conjecture C in
`docs/fable_el_genio.md`, found by the tour search and not exactly.
"""

from __future__ import annotations

import random
import time

import numpy as np
from cgshop2027_pyutils.grid import CellSet
from cgshop2027_pyutils.schemas import CGSHOP2027Solution
from scipy import ndimage

from ..catalog import cutter_cells, region_cells
from ..catalog import validator as make_validator
from . import lanes as _l
from ._tour import make_tour
from .refine import Refiner

REFINE_SHARE = _l.REFINE_SHARE
EIGHT = np.ones((3, 3), dtype=bool)


def _run_length(mask: np.ndarray) -> np.ndarray:
    """For every cell, the length of the row run that holds it (0 off the mask)."""
    H, W = mask.shape
    pad = np.zeros((H, W + 2), dtype=np.int8)
    pad[:, 1:-1] = mask
    d = np.diff(pad, axis=1).ravel()
    s, e = np.flatnonzero(d == 1), np.flatnonzero(d == -1)
    out = np.zeros(H * (W + 1) + 1, dtype=np.int64)
    np.add.at(out, s, e - s)
    np.add.at(out, e, s - e)
    return np.cumsum(out)[:-1].reshape(H, W + 1)[:, :W]


def _bridges(nodes: int, edges: list[tuple[int, int]]) -> np.ndarray:
    """Which edges of a multigraph are bridges (depth-first search, low links)."""
    adjacency: list[list[tuple[int, int]]] = [[] for _ in range(nodes)]
    for i, (a, b) in enumerate(edges):
        adjacency[a].append((b, i))
        adjacency[b].append((a, i))
    seen = np.full(nodes, -1, dtype=np.int64)
    low = np.zeros(nodes, dtype=np.int64)
    bridge = np.zeros(len(edges), dtype=bool)
    clock = 0
    for root in range(nodes):
        if seen[root] >= 0:
            continue
        seen[root] = low[root] = clock
        clock += 1
        stack = [(root, -1, 0)]
        while stack:
            v, via, at = stack.pop()
            if at < len(adjacency[v]):
                stack.append((v, via, at + 1))
                to, edge = adjacency[v][at]
                if edge == via:
                    continue
                if seen[to] >= 0:
                    low[v] = min(low[v], seen[to])
                else:
                    seen[to] = low[to] = clock
                    clock += 1
                    stack.append((to, edge, 0))
            elif via >= 0:
                a, b = edges[via]
                parent = a if b == v else b
                low[parent] = min(low[parent], low[v])
                if low[v] > seen[parent]:
                    bridge[via] = True
    return bridge


def zones(mask: np.ndarray, ch: int, cw: int) -> np.ndarray:
    """The cells of the thin corridors along the rows that lie on a cycle.

    Thin: the column run is longer than the cutter height and shorter than
    twice that, and the row run is at least three cutter widths.
    """
    tall = _run_length(np.ascontiguousarray(mask.T)).T
    wide = _run_length(mask)
    thin = mask & (tall > ch) & (tall < 2 * ch) & (wide >= 3 * cw)
    zone, count = ndimage.label(thin)
    if count == 0:
        return thin
    boxes = ndimage.find_objects(zone)
    long = np.array([False] + [b[1].stop - b[1].start >= 3 * cw for b in boxes])
    thin = long[zone]
    zone, count = ndimage.label(thin)
    if count == 0:
        return thin
    rest, others = ndimage.label(mask & ~thin)
    # A contact is a connected piece of the rest cells that touch a zone.
    near = ndimage.maximum_filter(zone, footprint=ndimage.generate_binary_structure(2, 1))
    fringe = (rest > 0) & (near > 0)
    contact, contacts = ndimage.label(fringe, structure=EIGHT)
    first = ndimage.find_objects(contact)
    edges = []
    for index, box in enumerate(first, start=1):
        ys, xs = np.nonzero(contact[box] == index)
        y, x = box[0].start + int(ys[0]), box[1].start + int(xs[0])
        edges.append((int(near[y, x]) - 1, count + int(rest[y, x]) - 1))
    bridge = _bridges(count + others, edges)
    on_cycle = np.zeros(count + 1, dtype=np.int64)
    for (z, _), is_bridge in zip(edges, bridge):
        on_cycle[z + 1] += not is_bridge
    return (on_cycle >= 2)[zone]


def _segments(region: CellSet, cutter: CellSet, zone: np.ndarray, piece: int) -> np.ndarray:
    """Lanes `(x0, y0, x1, y1)`: rows off the zone, columns on it, cut in pieces."""
    rows = _l._lanes(CellSet(region.mask & ~zone, region.origin), cutter)[1]
    teeth = _l._lanes(_l._transpose(CellSet(zone, region.origin)), _l._transpose(cutter))[1]
    out = []
    for y, a, b in rows.tolist():
        pieces = max(1, -(-(b - a + 1) // piece))
        for i in range(pieces):
            out.append((a + (b - a + 1) * i // pieces, y, a + (b - a + 1) * (i + 1) // pieces - 1, y))
    for x, a, b in teeth.tolist():
        out.append((x, a, x, b))
    return np.array(out, dtype=np.int64).reshape(-1, 4)


def _start(seg: np.ndarray, band: int) -> tuple[np.ndarray, np.ndarray]:
    """Bands of rows, each walked from one side to the other, alternating."""
    mid_y = (seg[:, 1] + seg[:, 3]) // 2
    mid_x = seg[:, 0] + seg[:, 2]
    row = mid_y // band
    sign = np.where(row % 2 == 0, 1, -1)
    order = np.lexsort((sign * mid_x, row)).astype(np.int64)
    flip = np.where(sign[order] > 0, 0, 1).astype(np.int64)
    upright = seg[order, 0] == seg[order, 2]
    flip[upright] = np.arange(len(order))[upright] % 2
    return order, flip


def _route(seg: np.ndarray, k: int, band: int, deadline: float):
    ex = np.ascontiguousarray(seg[:, [0, 2]].ravel())
    ey = np.ascontiguousarray(seg[:, [1, 3]].ravel())
    began = time.perf_counter()
    order, flip = _start(seg, band)
    _l._improve(order, flip, ex, ey, began + (0.75 if k > 1 else 1.0) * (deadline - began))
    if k > 1:
        parts, lengths = _l._settle(_l._split(order, flip, ex, ey, k), ex, ey, deadline)
    else:
        parts, lengths = [(order, flip)], [int(_l._tour_cost(order, flip, len(order), ex, ey))]
    paths = []
    for o, f in parts:
        points = []
        for v, turned in zip(o.tolist(), f.tolist()):
            i, j = 2 * v + turned, 2 * v + 1 - turned
            points.extend([(int(ex[i]), int(ey[i])), (int(ex[j]), int(ey[j]))])
        paths.append(_l._corner_path(points))
    return paths, lengths


def solve(instance, time_limit: float = 30.0, seed: int = 0, refine: bool = True):
    """Lanes in both orientations, chosen per corridor; falls back to `lanes`."""
    began = time.perf_counter()
    region = region_cells(instance)
    cutter = cutter_cells(instance)
    k = instance.number_of_cutters
    rng = random.Random(seed)
    _l._seed(seed)
    frames = []
    for flipped in (False, True):
        reg = _l._transpose(region) if flipped else region
        cut = _l._transpose(cutter) if flipped else cutter
        zone = zones(reg.mask.astype(bool), cut.height, cut.width) if len(region) else None
        if zone is not None and zone.any():
            frames.append((flipped, reg, cut, zone))
    if not frames:
        return _l.solve(instance, time_limit, seed, refine)
    route_until = began + time_limit * (1 - REFINE_SHARE if refine else 1.0)
    best, tried = None, {}
    for index, (flipped, reg, cut, zone) in enumerate(frames):
        seg = _segments(reg, cut, zone, 3 * max(cutter.width, cutter.height))
        share = (route_until - time.perf_counter()) / (len(frames) - index)
        paths, lengths = _route(seg, k, cut.height, time.perf_counter() + max(share, 0.05))
        if flipped:
            paths = [[(y, x) for x, y in path] for path in paths]
        name = "columns" if flipped else "rows"
        tried[name] = {"lanes": len(seg), "zone": int(zone.sum()), "max": max(lengths)}
        if best is None or max(lengths) < best[0]:
            best = (max(lengths), name, paths)
    _, chosen, paths = best
    meta = {"algorithm": "zigzag", "orientation": chosen, "tried": tried}
    def as_solution(paths):
        tours = [make_tour(path) for path in paths if path]
        park = paths[0][0] if paths and paths[0] else (0, 0)
        tours.extend(make_tour([park]) for _ in range(k - len(tours)))
        return CGSHOP2027Solution(instance_uid=instance.instance_uid, tours=tours, meta=meta)

    validator = make_validator(instance)
    solution = as_solution(paths)
    if validator.check_for_errors(solution):
        return _l.solve(instance, max(1.0, began + time_limit - time.perf_counter()), seed, refine)
    if refine:
        refiner = Refiner(region.mask, region.origin, list(cutter.cells()), [p for p in paths if p])
        refiner.run(began + time_limit, rng)
        candidate = as_solution(refiner.paths())
        if not validator.check_for_errors(candidate):
            meta["unrefined"] = solution.max_tour_length
            solution = candidate
    meta["seconds"] = round(time.perf_counter() - began, 1)
    return solution.model_copy(update={"meta": meta})
