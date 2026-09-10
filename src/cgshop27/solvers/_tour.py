"""Turning waypoints into a tour the schema accepts.

The schema wants axis-parallel edges, the implicit closing edge included, and
no point immediately repeating the one before it.
"""

from __future__ import annotations

from cgshop2027_pyutils.schemas import CutterTour

Point = tuple[int, int]


def axis_path(waypoints: list[Point]) -> list[Point]:
    """Connect waypoints with axis-parallel moves, going vertically first."""
    if not waypoints:
        return []
    path = [waypoints[0]]
    for x, y in waypoints[1:]:
        px, py = path[-1]
        if px != x and py != y:
            path.append((px, y))  # the corner of the L
        path.append((x, y))
    return path


def _redundant(a: Point, b: Point, c: Point) -> bool:
    """True when dropping `b` leaves the walked path unchanged.

    Being collinear with its neighbours is not enough: a point where the path
    turns back on itself is collinear too, and dropping it would cut the reach
    of the sweep short. `b` has to lie *between* `a` and `c`.
    """
    if a[0] == b[0] == c[0]:
        return min(a[1], c[1]) <= b[1] <= max(a[1], c[1])
    if a[1] == b[1] == c[1]:
        return min(a[0], c[0]) <= b[0] <= max(a[0], c[0])
    return False


def close_tour(path: list[Point]) -> list[Point]:
    """Make the wrap-around edge axis-parallel, then drop redundant corners."""
    points = [p for i, p in enumerate(path) if i == 0 or p != path[i - 1]]
    if len(points) < 2:
        return points[:1]

    first, last = points[0], points[-1]
    if first[0] != last[0] and first[1] != last[1]:
        points.append((first[0], last[1]))

    # Merge collinear runs, including across the wrap-around.
    merged: list[Point] = []
    for point in points:
        while len(merged) >= 2 and _redundant(merged[-2], merged[-1], point):
            merged.pop()
        if merged and merged[-1] == point:
            continue
        merged.append(point)
    while len(merged) >= 3 and _redundant(merged[-2], merged[-1], merged[0]):
        merged.pop()
    while len(merged) >= 3 and _redundant(merged[-1], merged[0], merged[1]):
        merged.pop(0)
    if len(merged) >= 2 and merged[0] == merged[-1]:
        merged.pop()
    return merged or points[:1]


def make_tour(waypoints: list[Point]) -> CutterTour:
    points = close_tour(axis_path(waypoints))
    return CutterTour(x=[p[0] for p in points], y=[p[1] for p in points])
