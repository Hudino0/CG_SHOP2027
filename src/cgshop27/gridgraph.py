"""Drawing the dual grid graph that the tile-based solver works on.

The `fekete` solver cuts the region into `s x s` blocks. Each block that holds
at least one region cell is a node; two nodes are joined when their blocks
share a side. That is the grid graph of the paper of Fekete et al., and step A
of the solver looks for a round trip on it. The picture shows:

- the region cells (green),
- the block grid at the offset the solver picks (fewest blocks),
- the nodes: full blocks in white, blocks that the region only partly fills
  in yellow,
- the edges between grid neighbours,
- optionally the tours of a run on top, one color per cutter.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.collections import LineCollection  # noqa: E402
from cgshop2027_pyutils.schemas import CGSHOP2027Instance, CGSHOP2027Solution  # noqa: E402

from .catalog import cutter_cells, region_cells  # noqa: E402
from .config import OUT  # noqa: E402
from .solvers.fekete import _block_sizes, _tiles, grid_shifts  # noqa: E402

GRIDS = OUT / "grids"
TOUR_COLORS = ("#1f77b4", "#d62728", "#9467bd", "#ff7f0e", "#17becf")


def block_size(instance: CGSHOP2027Instance, solution: CGSHOP2027Solution | None) -> int:
    """The block size of a `fekete` solution, else the largest the solver tries."""
    meta = (solution.meta or {}) if solution is not None else {}
    if "block_size" in meta:
        return int(meta["block_size"])
    return _block_sizes(cutter_cells(instance))[-1]


def draw(
    instance: CGSHOP2027Instance,
    solution: CGSHOP2027Solution | None = None,
    *,
    s: int | None = None,
    target: Path,
    dpi: int = 110,
) -> tuple[Path, dict]:
    region = region_cells(instance)
    s = s or block_size(instance, solution)
    count, (shift_x, shift_y) = grid_shifts(region, s)[0]
    tiles = _tiles(region.mask, s, shift_x, shift_y)
    filled = tiles.sum(axis=(2, 3))
    by, bx = np.nonzero(filled)
    full = filled[by, bx] == s * s
    ox, oy = region.origin[0] - shift_x, region.origin[1] - shift_y
    cx = ox + bx * s + s / 2
    cy = oy + by * s + s / 2

    occupied = filled > 0
    edges = []
    for dy, dx in ((0, 1), (1, 0)):
        a = occupied[: occupied.shape[0] - dy, : occupied.shape[1] - dx]
        b = occupied[dy:, dx:]
        ys, xs = np.nonzero(a & b)
        for y, x in zip(ys, xs):
            p = (ox + x * s + s / 2, oy + y * s + s / 2)
            edges.append((p, (p[0] + dx * s, p[1] + dy * s)))

    height, width = region.mask.shape
    x0, y0 = region.origin
    span = max(width, height)
    fig, ax = plt.subplots(figsize=(10, 10 * height / width if width >= height else 10))
    ax.imshow(region.mask, origin="lower", cmap=matplotlib.colors.ListedColormap(["white", "#a8d5a2"]),
              extent=(x0, x0 + width, y0, y0 + height), interpolation="nearest", zorder=0)

    # The block grid, only as far as the occupied blocks reach.
    rows, cols = occupied.shape
    lines = [((ox + i * s, oy), (ox + i * s, oy + rows * s)) for i in range(cols + 1)]
    lines += [((ox, oy + j * s), (ox + cols * s, oy + j * s)) for j in range(rows + 1)]
    ax.add_collection(LineCollection(lines, colors="#6b8f68", linewidths=0.4, zorder=1))
    ax.add_collection(LineCollection(edges, colors="#333333", linewidths=0.8, zorder=2))
    size = max(4.0, 1600 / span * s / 4)
    ax.scatter(cx[full], cy[full], s=size, c="white", edgecolors="#333333", linewidths=0.5, zorder=3)
    ax.scatter(cx[~full], cy[~full], s=size, c="#ffd166", edgecolors="#333333", linewidths=0.5, zorder=3)

    tours = 0
    if solution is not None:
        for i, tour in enumerate(solution.tours):
            xs, ys = list(tour.x) + [tour.x[0]], list(tour.y) + [tour.y[0]]
            ax.plot(xs, ys, color=TOUR_COLORS[i % len(TOUR_COLORS)], lw=1.4, alpha=0.85, zorder=4)
            tours += 1

    stats = {
        "block_size": s,
        "shift": (shift_x, shift_y),
        "nodes": int(len(bx)),
        "full_nodes": int(full.sum()),
        "edges": len(edges),
    }
    title = (f"{instance.instance_uid}  ·  bloques {s}x{s}  ·  {stats['nodes']} nodos "
             f"({stats['full_nodes']} llenos)  ·  {stats['edges']} aristas")
    if tours:
        title += f"  ·  max tour {solution.max_tour_length}"
    ax.set_title(title, fontsize=10)
    ax.set_aspect("equal")
    ax.set_xlim(min(ox, x0) - 1, max(ox + cols * s, x0 + width) + 1)
    ax.set_ylim(min(oy, y0) - 1, max(oy + rows * s, y0 + height) + 1)
    ax.tick_params(labelsize=7)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        fig.savefig(target, dpi=dpi, bbox_inches="tight")
    finally:
        plt.close(fig)
    return target, stats
