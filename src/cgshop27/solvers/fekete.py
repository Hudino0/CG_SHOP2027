"""The tile-based lawn mowing method of Fekete, Krupke, Perk, Rieck and Scheffer.

Reference: S. P. Fekete, D. Krupke, M. Perk, C. Rieck, C. Scheffer. "The Lawn
Mowing Problem: From Algebra to Algorithms". ESA 2023, arXiv:2307.01092.

The paper mows a polyomino with a disk of diameter 1 in three steps (its
Section 3.4 and Section 5):

A. Find a cheap round trip on the dual grid graph of the pixels (TSP).
B. Replace each pixel visit by a *puzzle piece*: a short path between the
   transition points on the pixel's sides that covers the whole pixel. A
   straight pass is free, a turn and a U-turn cost extra (the "turn cost").
C. Improve the tour against the true cost, turn cost included (TSP_Turn).

The cutters of CG:SHOP 2027 are discrete disks (squares, diamonds, rounded
squares), so the method carries over nearly one to one. What changes:

- Pixels become *blocks* of `s x s` cells. `s` runs from the largest square
  inside the cutter (the paper's TSP_Small: the center point alone covers a
  block and turns are free) up to the cutter width (the paper's TSP_Cov:
  straight passes cover a block, turns need puzzle pieces). The grid offset is
  the one with the fewest blocks (Section 5.1.1). Every size gets a short
  race; the best one gets the rest of the time and goes on from its tour.
- Puzzle pieces are computed, not derived by hand: for each block content and
  each pair of sides, `_Pieces` finds the shortest lattice path with up to two
  intermediate points whose sweep covers the block, by enumerating candidates
  in order of length. It works for any cutter shape.
- Step A uses a Warnsdorff walk that prefers to go straight, not Concorde.
- Step C uses 2-opt and Or-opt moves evaluated against the exact tour cost
  (block pieces included), not the Gurobi IP inside an LNS. The piece lengths
  and the whole search run compiled (`_blockls`).
- The contest wants `k` tours and scores the longest one. The single tour is
  cut into `k` balanced pieces (tour splitting), each piece is closed and
  improved again, and blocks move between tours to balance them.
- A last pass uses the exact coverage: it drops a block visit, or swaps its
  covering piece for the plain path, when the neighbours already sweep its
  cells. Pieces are conservative by design, so this recovers overlap.
- Then the tours leave the blocks behind: `refine` shortens the lattice walks
  themselves against the exact coverage of all tours (shortcuts, and lanes
  and U-turns that slide toward the border).

Every result is checked with the official validator before it is returned.
"""

from __future__ import annotations

import random
import time
from itertools import product

import numpy as np
from cgshop2027_pyutils.grid import CellSet
from cgshop2027_pyutils.schemas import CGSHOP2027Instance, CGSHOP2027Solution
from cgshop2027_pyutils.verify import SolutionValidator

from ..catalog import cutter_cells, region_cells
from ._blockls import Tour, order_cost, piece_table, seed_rng
from ._tour import Point, make_tour
from .refine import Refiner

# The part of each block size's time that goes to the lattice refiner.
REFINE_SHARE = 0.15
# The part of the time that the block sizes race for before the best goes on.
RACE_SHARE = 0.35

# The sides of a block where a piece starts or ends. `J` is the block's own
# center: the piece of a block whose tour neighbour is not a grid neighbour.
L, R, B, T, J = range(5)
_SIDE = {(-1, 0): L, (1, 0): R, (0, -1): B, (0, 1): T}


def _l1(a: Point, b: Point) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _corners(a: Point, b: Point) -> tuple[list[Point], ...]:
    """The axis-parallel walks from `a` to `b` with at most one corner.

    Each walk is given as the points after `a`. Vertical-first comes first,
    which is also how `_jump` and `axis_path` connect far points.
    """
    if a[0] == b[0] or a[1] == b[1]:
        return ([b],)
    return ([(a[0], b[1]), b], [(b[0], a[1]), b])


def _jump(a: Point, b: Point) -> list[Point]:
    return [a, *_corners(a, b)[0]]


# -- step B: puzzle pieces -------------------------------------------------


class _Pieces:
    """Shortest covering paths through one block, per block content.

    Coordinates are relative to the block's lower-left cell. A block's cells
    are the bits `y * s + x` of an int; `mask` holds the ones inside the
    region, the only ones that need cover.
    """

    def __init__(self, offsets: list[Point], s: int) -> None:
        self.s = s
        self.offsets = offsets
        xs = [dx for dx, _ in offsets]
        ys = [dy for _, dy in offsets]
        # Center the cutter on the block, so the center point covers the most.
        cx = -min(xs) + (s - (max(xs) - min(xs) + 1)) // 2
        cy = -min(ys) + (s - (max(ys) - min(ys) + 1)) // 2
        self.center = (cx, cy)
        # The points whose stamp touches the block at all.
        self.window = [
            (x, y)
            for y in range(-max(ys), s - min(ys))
            for x in range(-max(xs), s - min(xs))
        ]
        self._stamp: dict[Point, int] = {}
        self._segment: dict[tuple[Point, Point], int] = {}
        self._walks: dict[tuple[Point, Point], list[tuple[int, list[Point]]]] = {}

        # The paper puts the transition points at the side centers. On the
        # lattice the center of a side is ambiguous, so take the placement
        # whose turns and U-turns are cheapest on a full block.
        full = (1 << (s * s)) - 1
        best = None
        for shift in range(s + 1):
            self._place(shift)
            turns = sum(
                self.piece(full, a, b)[0] for a in range(4) for b in range(a, 4)
            )
            if best is None or turns < best[0]:
                best = (turns, shift)
        self._place(best[1])

    def _place(self, shift: int) -> None:
        cx, cy = self.center
        s = self.s
        # Neighbouring blocks sit `s` apart, so the right end of a block is
        # the left end of its right neighbour: pieces chain without a gap.
        self.ends = {
            L: (cx - s + shift, cy),
            R: (cx + shift, cy),
            B: (cx, cy - s + shift),
            T: (cx, cy + shift),
            J: (cx, cy),
        }
        self._cache: dict[tuple[int, int, int], tuple[int, list[Point]]] = {}

    def stamp(self, p: Point) -> int:
        bits = self._stamp.get(p)
        if bits is None:
            bits = 0
            s = self.s
            for dx, dy in self.offsets:
                x, y = p[0] + dx, p[1] + dy
                if 0 <= x < s and 0 <= y < s:
                    bits |= 1 << (y * s + x)
            self._stamp[p] = bits
        return bits

    def segment(self, a: Point, b: Point) -> int:
        """The cells swept along an axis-parallel segment."""
        key = (a, b) if a <= b else (b, a)
        bits = self._segment.get(key)
        if bits is None:
            (x0, y0), (x1, y1) = key
            bits = 0
            if x0 == x1:
                for y in range(min(y0, y1), max(y0, y1) + 1):
                    bits |= self.stamp((x0, y))
            else:
                for x in range(x0, x1 + 1):
                    bits |= self.stamp((x, y0))
            self._segment[key] = bits
        return bits

    def walks(self, a: Point, b: Point) -> list[tuple[int, list[Point]]]:
        """Each walk from `a` to `b` with the cells it sweeps."""
        key = (a, b)
        found = self._walks.get(key)
        if found is None:
            found = []
            for points in _corners(a, b):
                bits, previous = self.stamp(a), a
                for point in points:
                    bits |= self.segment(previous, point)
                    previous = point
                found.append((bits, points))
            self._walks[key] = found
        return found

    def piece(self, mask: int, a: int, b: int) -> tuple[int, list[Point]]:
        """The shortest covering path from side `a` to side `b`."""
        flip = a > b
        key = (mask, b, a) if flip else (mask, a, b)
        found = self._cache.get(key)
        if found is None:
            found = self._search(mask, self.ends[key[1]], self.ends[key[2]])
            self._cache[key] = found
        if flip:
            return found[0], found[1][::-1]
        return found

    def plain(self, a: int, b: int) -> tuple[int, list[Point]]:
        """The shortest path from side `a` to side `b`, covering or not."""
        start, end = self.ends[a], self.ends[b]
        return _l1(start, end), [start, *_corners(start, end)[0]]

    def _cover(self, mask: int, route: list[Point]) -> list[Point] | None:
        """A realization of `route` that covers `mask`, or None."""
        options = [self.walks(route[i], route[i + 1]) for i in range(len(route) - 1)]
        for choice in product(*options):
            bits = self.stamp(route[0])
            for leg_bits, _ in choice:
                bits |= leg_bits
            if bits & mask == mask:
                path = [route[0]]
                for _, points in choice:
                    path.extend(points)
                return path
        return None

    def _search(self, mask: int, start: Point, end: Point) -> tuple[int, list[Point]]:
        # Routes through 0, 1 or 2 intermediate points, shortest first; the
        # first one that covers is optimal among them. Most blocks settle
        # with 0 or 1 point, so the pairs are only scanned below that length.
        path = self._cover(mask, [start, end])
        if path is not None:
            return _l1(start, end), path

        useful = [q for q in self.window if self.stamp(q) & mask]
        if self.center not in useful:
            useful.append(self.center)
        best = None
        for q in sorted(useful, key=lambda q: _l1(start, q) + _l1(q, end)):
            path = self._cover(mask, [start, q, end])
            if path is not None:
                best = (_l1(start, q) + _l1(q, end), path)
                break

        points = np.array(useful)
        to_q = np.abs(points - start).sum(axis=1)
        from_q = np.abs(points - end).sum(axis=1)
        between = np.abs(points[:, None, :] - points[None, :, :]).sum(axis=2)
        lengths = (to_q[:, None] + between + from_q[None, :]).ravel()
        shorter = np.nonzero(lengths < best[0])[0] if best else np.arange(lengths.size)
        count = len(useful)
        for index in shorter[np.argsort(lengths[shorter], kind="stable")].tolist():
            first, second = divmod(index, count)
            if first == second:
                continue
            path = self._cover(mask, [start, useful[first], useful[second], end])
            if path is not None:
                return int(lengths[index]), path
        return best or self._greedy(mask, start, end)

    def _greedy(self, mask: int, start: Point, end: Point) -> tuple[int, list[Point]]:
        """Fallback for odd cutters: add the point that covers most, cheapest."""
        route = [start, end]
        while True:
            path = [route[0]]
            bits = self.stamp(route[0])
            for i in range(len(route) - 1):
                leg_bits, points = self.walks(route[i], route[i + 1])[0]
                bits |= leg_bits
                path.extend(points)
            missing = mask & ~bits
            if not missing:
                length = sum(_l1(path[i], path[i + 1]) for i in range(len(path) - 1))
                return length, path
            best = max(self.window, key=lambda p: (self.stamp(p) & missing).bit_count())
            spot = min(
                range(len(route) - 1),
                key=lambda i: _l1(route[i], best) + _l1(best, route[i + 1])
                - _l1(route[i], route[i + 1]),
            )
            route.insert(spot + 1, best)


# -- the block grid and the tour cost --------------------------------------


def _tiles(mask: np.ndarray, s: int, shift_x: int, shift_y: int) -> np.ndarray:
    """The region cut into s x s blocks, shifted by (shift_x, shift_y)."""
    height, width = mask.shape
    rows = -(-(height + shift_y) // s)
    cols = -(-(width + shift_x) // s)
    padded = np.zeros((rows * s, cols * s), dtype=bool)
    padded[shift_y : shift_y + height, shift_x : shift_x + width] = mask
    return padded.reshape(rows, s, cols, s).transpose(0, 2, 1, 3)


def grid_shifts(region: CellSet, s: int) -> list[tuple[int, Point]]:
    """Every grid offset with its block count, fewest blocks first."""
    counts = []
    for shift_y in range(s):
        for shift_x in range(s):
            tiles = _tiles(region.mask, s, shift_x, shift_y)
            counts.append((int(tiles.any(axis=(2, 3)).sum()), (shift_x, shift_y)))
    return sorted(counts)


class _Model:
    """Blocks of one size, their puzzle pieces, and the exact tour cost."""

    def __init__(self, region: CellSet, offsets: list[Point], s: int, shift: Point | None = None) -> None:
        self.s = s
        self.pieces = _Pieces(offsets, s)
        # Section 5.1.1: the grid offset with the fewest blocks, unless given.
        shifts = grid_shifts(region, s)
        shift_x, shift_y = shift if shift is not None else shifts[0][1]
        tiles = _tiles(region.mask, s, shift_x, shift_y)
        self.ox = region.origin[0] - shift_x
        self.oy = region.origin[1] - shift_y

        weights = np.array([1 << i for i in range(s * s)], dtype=object)
        occupied = tiles.any(axis=(2, 3))
        by, bx = np.nonzero(occupied)
        self.bx: list[int] = bx.tolist()
        self.by: list[int] = by.tolist()
        self.n = len(self.bx)
        self.index = {(x, y): v for v, (x, y) in enumerate(zip(self.bx, self.by))}

        self.masks: list[int] = []
        mask_ids: dict[int, int] = {}
        self.mid: list[int] = []
        for x, y in zip(self.bx, self.by):
            bits = int(tiles[y, x].reshape(-1).astype(object).dot(weights))
            if bits not in mask_ids:
                mask_ids[bits] = len(self.masks)
                self.masks.append(bits)
            self.mid.append(mask_ids[bits])

        self.near4 = [self._around(v, ((1, 0), (-1, 0), (0, 1), (0, -1))) for v in range(self.n)]
        eight = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))
        self.near8 = [self._around(v, eight) for v in range(self.n)]
        self._fill_isolated()
        self._length: dict[tuple[int, int, int], int] = {}
        self.G = self._compile()

    def _compile(self) -> tuple:
        """Every piece length up front, and the arrays of the compiled search."""
        table = piece_table(self.pieces, self.masks)
        for mid, a, b in zip(*np.nonzero(table < 0)):
            table[mid, a, b] = self.pieces.piece(self.masks[mid], int(a), int(b))[0]
        for (mid, a, b), length in np.ndenumerate(table):
            self._length[(mid, a, b)] = int(length)

        def padded(lists: list[list[int]]) -> np.ndarray:
            out = np.full((self.n, max(1, max(map(len, lists), default=1))), -1, dtype=np.int64)
            for v, near in enumerate(lists):
                out[v, : len(near)] = near
            return out

        bx = np.array(self.bx, dtype=np.int64)
        by = np.array(self.by, dtype=np.int64)
        grid = np.full((int(by.max()) + 1, int(bx.max()) + 1), -1, dtype=np.int64)
        grid[by, bx] = np.arange(self.n)
        mid = np.array(self.mid, dtype=np.int64)
        return (bx, by, mid, table, np.int64(self.s), padded(self.near4), padded(self.near8), grid)

    def tour(self, order: list[int]) -> Tour:
        return Tour(self.G, self.n, order)

    def _around(self, v: int, steps) -> list[int]:
        x, y = self.bx[v], self.by[v]
        return [w for dx, dy in steps if (w := self.index.get((x + dx, y + dy))) is not None]

    def _fill_isolated(self) -> None:
        """Blocks with few grid neighbours get their nearest blocks instead."""
        coords = np.array([self.bx, self.by]).T
        for v in range(self.n):
            if len(self.near8) and len(self.near8[v]) >= 3:
                continue
            distance = np.abs(coords - coords[v]).sum(axis=1)
            distance[v] = 1 << 30
            nearest = np.argsort(distance, kind="stable")[:6].tolist()
            self.near8[v] = list(dict.fromkeys(self.near8[v] + nearest))

    # cost -----------------------------------------------------------------

    def side(self, v: int, u: int) -> int:
        return _SIDE.get((self.bx[u] - self.bx[v], self.by[u] - self.by[v]), J)

    def piece_length(self, v: int, a: int, b: int) -> int:
        key = (self.mid[v], a, b)
        length = self._length.get(key)
        if length is None:
            length = self.pieces.piece(self.masks[key[0]], a, b)[0]
            self._length[key] = length
            self._length[(key[0], b, a)] = length
        return length

    def bc(self, v: int, u: int, w: int) -> int:
        """The cost of the piece in block `v` between tour neighbours u and w."""
        return self.piece_length(v, self.side(v, u), self.side(v, w))

    def ec(self, u: int, v: int) -> int:
        """Travel between consecutive blocks: free between grid neighbours."""
        steps = abs(self.bx[u] - self.bx[v]) + abs(self.by[u] - self.by[v])
        return 0 if steps == 1 else self.s * steps

    def cost(self, order: list[int]) -> int:
        n = len(order)
        if n == 0:
            return 0
        if n == 1:
            return self.piece_length(order[0], J, J)
        if n > 2:
            return order_cost(self.G, np.asarray(order, dtype=np.int64))
        total = 0
        for i, v in enumerate(order):
            w = order[(i + 1) % n]
            total += self.bc(v, order[i - 1], w) + self.ec(v, w)
        return total

    # geometry -------------------------------------------------------------

    def block_origin(self, v: int) -> Point:
        return (self.ox + self.bx[v] * self.s, self.oy + self.by[v] * self.s)

    def center(self, v: int) -> Point:
        x, y = self.block_origin(v)
        return (x + self.pieces.center[0], y + self.pieces.center[1])

    def piece_path(self, v: int, a: int, b: int, plain: bool = False) -> list[Point]:
        if plain:
            _, path = self.pieces.plain(a, b)
        else:
            _, path = self.pieces.piece(self.masks[self.mid[v]], a, b)
        x, y = self.block_origin(v)
        return [(x + px, y + py) for px, py in path]

    # step A ---------------------------------------------------------------

    def initial_order(self) -> list[int]:
        """A Warnsdorff walk over the block grid that prefers going straight.

        Moving to the neighbour with the fewest unvisited neighbours keeps the
        walk from stranding blocks, so it jumps rarely. When it is stuck it
        jumps to the nearest unvisited block.
        """
        n = self.n
        coords = np.array([self.bx, self.by]).T
        visited = np.zeros(n, dtype=bool)
        degree = [len(near) for near in self.near4]
        current = min(range(n), key=lambda v: (degree[v], self.by[v], self.bx[v]))
        heading = None
        order: list[int] = []
        while True:
            visited[current] = True
            order.append(current)
            for w in self.near4[current]:
                degree[w] -= 1
            if len(order) == n:
                return order
            options = [w for w in self.near4[current] if not visited[w]]
            if options:
                step = min(
                    options,
                    key=lambda w: (
                        degree[w],
                        (self.bx[w] - self.bx[current], self.by[w] - self.by[current]) != heading,
                    ),
                )
            else:
                distance = np.abs(coords - coords[current]).sum(axis=1)
                distance[visited] = 1 << 30
                step = int(np.argmin(distance))
            heading = (self.bx[step] - self.bx[current], self.by[step] - self.by[current])
            current = step

    def strip_order(self, horizontal: bool) -> list[int]:
        """Runs of blocks along rows (or columns), chained nearest end first.

        This is the shape of the TSP_Turn tours in the paper's Figure 11:
        long straight passes, few turns. The local search then fixes the
        seams between the runs.
        """
        major = self.by if horizontal else self.bx
        minor = self.bx if horizontal else self.by
        runs: list[list[int]] = []
        for v in sorted(range(self.n), key=lambda v: (major[v], minor[v])):
            if runs and major[runs[-1][-1]] == major[v] and minor[runs[-1][-1]] + 1 == minor[v]:
                runs[-1].append(v)
            else:
                runs.append([v])
        heads = np.array([[self.bx[r[0]], self.by[r[0]]] for r in runs])
        tails = np.array([[self.bx[r[-1]], self.by[r[-1]]] for r in runs])
        used = np.zeros(len(runs), dtype=bool)
        order: list[int] = []
        index, forward = 0, True
        while True:
            used[index] = True
            order.extend(runs[index] if forward else runs[index][::-1])
            if used.all():
                return order
            here = np.array([self.bx[order[-1]], self.by[order[-1]]])
            to_head = np.abs(heads - here).sum(axis=1)
            to_tail = np.abs(tails - here).sum(axis=1)
            to_head[used] = to_tail[used] = 1 << 30
            head, tail = int(np.argmin(to_head)), int(np.argmin(to_tail))
            if to_head[head] <= to_tail[tail]:
                index, forward = head, True
            else:
                index, forward = tail, False


# -- step C: local search against the exact cost (compiled in _blockls) ------


class _Ring:
    """A closed tour with positions, for the move costs of `_balance`.

    The search itself (2-opt, Or-opt, LNS) runs compiled in `_blockls`.
    """

    def __init__(self, model: _Model, order: list[int]) -> None:
        self.m = model
        self.t = list(order)
        self.n = len(order)
        self.pos = {v: i for i, v in enumerate(self.t)}

    def succ(self, v: int) -> int:
        i = self.pos[v] + 1
        return self.t[i if i < self.n else 0]

    def pred(self, v: int) -> int:
        return self.t[self.pos[v] - 1]

    def order(self) -> list[int]:
        return list(self.t)

    def insertion(self, v: int, c: int, d: int) -> int:
        """Cost change of putting `v` (not in the tour) between c and d."""
        m = self.m
        return (
            m.ec(c, v) + m.ec(v, d) - m.ec(c, d) + m.bc(v, c, d)
            + m.bc(c, self.pred(c), v) - m.bc(c, self.pred(c), d)
            + m.bc(d, v, self.succ(d)) - m.bc(d, c, self.succ(d))
        )

    def removal(self, v: int) -> int:
        """Cost change of taking `v` out of the tour."""
        m = self.m
        if self.n <= 3:
            return m.cost([x for x in self.t if x != v]) - m.cost(self.t)
        u, w = self.pred(v), self.succ(v)
        return (
            m.ec(u, w) - m.ec(u, v) - m.ec(v, w) - m.bc(v, u, w)
            + m.bc(u, self.pred(u), w) - m.bc(u, self.pred(u), v)
            + m.bc(w, u, self.succ(w)) - m.bc(w, v, self.succ(w))
        )


def _lns(model: _Model, order: list[int], deadline: float, rng: random.Random) -> list[int]:
    """Large neighbourhood search, as in the paper's Section 5.1.4.

    Pick a random block, take out every block of the tour in a small square
    around it, put them back one by one at their cheapest place, and let the
    local search settle the neighbourhood. Keep the result unless it is
    worse; equal cost is accepted, so the tour can drift across plateaus.
    The loop runs compiled (`_blockls.lns`) in batches that fit the deadline.
    """
    tour = model.tour(order)
    if len(order) < 12:
        return tour.order()
    batch = 8
    while (now := time.perf_counter()) < deadline:
        tour.lns(batch)
        spent = time.perf_counter() - now
        # Aim for batches of about 20 ms, so the deadline is kept closely.
        batch = max(1, min(4 * batch, int(batch * 0.02 / max(spent, 1e-4))))
    return tour.order()


# -- k tours ---------------------------------------------------------------


def _split(model: _Model, order: list[int], k: int) -> list[list[int]]:
    """Cut the closed tour into at most `k` closed tours of balanced cost."""
    n = len(order)
    if k <= 1 or n <= 1:
        return [order]
    if n <= k:
        return [[v] for v in order]

    doubled = order + order
    block = [model.bc(doubled[i], doubled[i - 1], doubled[i + 1]) for i in range(2 * n - 1)]
    block.append(0)
    edge = [model.ec(doubled[i], doubled[i + 1]) for i in range(2 * n - 1)] + [0]
    block_sum = np.concatenate(([0], np.cumsum(block))).tolist()
    edge_sum = np.concatenate(([0], np.cumsum(edge))).tolist()

    def chunk(i: int, size: int) -> int:
        if size <= 2:
            return model.cost(doubled[i : i + size])
        j = i + size - 1
        first, last = doubled[i], doubled[j]
        return (
            block_sum[j] - block_sum[i + 1]
            + edge_sum[j] - edge_sum[i]
            + model.bc(first, last, doubled[i + 1])
            + model.bc(last, doubled[j - 1], first)
            + model.ec(last, first)
        )

    def cuts(start: int, limit: int) -> list[int] | None:
        sizes, at, end = [], start, start + n
        while at < end:
            if chunk(at, 1) > limit or len(sizes) == k:
                return None
            low, high = 1, end - at
            while low < high:
                middle = (low + high + 1) // 2
                if chunk(at, middle) <= limit:
                    low = middle
                else:
                    high = middle - 1
            sizes.append(low)
            at += low
        return sizes

    best = None
    starts = sorted(set(np.linspace(0, n - 1, min(n, 96)).astype(int).tolist()))
    ceiling = model.cost(order) + model.s * n
    for start in starts:
        low, high = 0, ceiling
        found = None
        while low <= high:
            middle = (low + high) // 2
            sizes = cuts(start, middle)
            if sizes is None:
                low = middle + 1
            else:
                found, high = (middle, sizes), middle - 1
        if found and (best is None or found[0] < best[0]):
            best = (found[0], start, found[1])
    _, start, sizes = best
    tours, at = [], start
    for size in sizes:
        tours.append(doubled[at : at + size])
        at += size
    return tours


def _balance(model: _Model, tours: list[list[int]], deadline: float) -> list[list[int]]:
    """Move single blocks out of the longest tour into a bordering one."""
    rings = [_Ring(model, tour) for tour in tours]
    owner = {v: i for i, tour in enumerate(tours) for v in tour}
    costs = [model.cost(tour) for tour in tours]

    def insertion(ring: _Ring, v: int, y: int, z: int) -> int:
        if ring.n <= 2:
            at = ring.t.index(y)
            return model.cost(ring.t[: at + 1] + [v] + ring.t[at + 1 :]) - model.cost(ring.t)
        return ring.insertion(v, y, z)

    while time.perf_counter() < deadline:
        worst = max(range(len(rings)), key=costs.__getitem__)
        ring = rings[worst]
        if ring.n <= 1:
            break
        best = None
        for v in ring.t:
            lighter = costs[worst] + ring.removal(v)
            if lighter >= costs[worst]:
                continue
            for x in model.near4[v]:
                other = owner.get(x, worst)
                if other == worst:
                    continue
                target = rings[other]
                for y, z in ((x, target.succ(x)), (target.pred(x), x)):
                    heavier = costs[other] + insertion(target, v, y, z)
                    peak = max(lighter, heavier)
                    if peak < costs[worst] and (best is None or peak < best[0]):
                        best = (peak, v, other, y)
        if best is None:
            break
        _, v, other, y = best
        shrunk = [x for x in ring.t if x != v]
        grown = list(rings[other].t)
        grown.insert(grown.index(y) + 1, v)
        rings[worst], rings[other] = _Ring(model, shrunk), _Ring(model, grown)
        costs[worst], costs[other] = model.cost(shrunk), model.cost(grown)
        owner[v] = other
    return [ring.order() for ring in rings]


# -- exact coverage and pruning ---------------------------------------------


class _Coverage:
    """How often each region cell is swept, for incremental checks."""

    def __init__(self, region: CellSet, offsets: list[Point]) -> None:
        self.region = region.mask
        self.origin = region.origin
        self.count = np.zeros(region.mask.shape, dtype=np.int32)
        self.offsets = offsets
        self.dx0 = min(dx for dx, _ in offsets)
        self.dy0 = min(dy for _, dy in offsets)
        self.cw = max(dx for dx, _ in offsets) - self.dx0 + 1
        self.ch = max(dy for _, dy in offsets) - self.dy0 + 1

    def add(self, path: list[Point], sign: int) -> tuple[slice, slice] | None:
        xs = [p[0] for p in path]
        ys = [p[1] for p in path]
        x0, y0 = min(xs), min(ys)
        w, h = max(xs) - x0 + 1, max(ys) - y0 + 1
        points = np.zeros((h, w), dtype=bool)
        points[path[0][1] - y0, path[0][0] - x0] = True
        for (ax, ay), (bx, by) in zip(path, path[1:]):
            points[min(ay, by) - y0 : max(ay, by) - y0 + 1, min(ax, bx) - x0 : max(ax, bx) - x0 + 1] = True
        swept = np.zeros((h + self.ch - 1, w + self.cw - 1), dtype=bool)
        for dx, dy in self.offsets:
            ox, oy = dx - self.dx0, dy - self.dy0
            swept[oy : oy + h, ox : ox + w] |= points
        # Place it on the region grid, clipped.
        left = x0 + self.dx0 - self.origin[0]
        bottom = y0 + self.dy0 - self.origin[1]
        rows = slice(max(bottom, 0), min(bottom + swept.shape[0], self.count.shape[0]))
        cols = slice(max(left, 0), min(left + swept.shape[1], self.count.shape[1]))
        if rows.start >= rows.stop or cols.start >= cols.stop:
            return None
        part = swept[rows.start - bottom : rows.stop - bottom, cols.start - left : cols.stop - left]
        self.count[rows, cols] += sign * part.astype(np.int32)
        return rows, cols

    def covered(self, windows) -> bool:
        for window in windows:
            if window is None:
                continue
            rows, cols = window
            if np.any(self.region[rows, cols] & (self.count[rows, cols] <= 0)):
                return False
        return True


class _Pruner:
    """Drop block visits and covering detours the neighbours make redundant.

    The tours are linked lists here, so dropping a block costs O(1).
    """

    def __init__(self, model: _Model, tours: list[list[int]], coverage: _Coverage) -> None:
        self.m = model
        self.plain: set[int] = set()
        self.cov = coverage
        self.nxt: dict[int, int] = {}
        self.prv: dict[int, int] = {}
        self.size: list[int] = []
        self.owner: dict[int, int] = {}
        for index, tour in enumerate(tours):
            self.size.append(len(tour))
            for i, v in enumerate(tour):
                self.nxt[v] = tour[(i + 1) % len(tour)]
                self.prv[v] = tour[i - 1]
                self.owner[v] = index
        for tour in tours:
            for path in self._units(tour):
                coverage.add(path, +1)

    def tours(self) -> list[list[int]]:
        heads: dict[int, int] = {}
        for v, index in self.owner.items():
            heads.setdefault(index, v)
        result = []
        for index in range(len(self.size)):
            if index not in heads:
                continue
            tour, v = [heads[index]], self.nxt[heads[index]]
            while v != tour[0]:
                tour.append(v)
                v = self.nxt[v]
            result.append(tour)
        return result

    def _piece(self, v: int, u: int | None, w: int | None) -> list[Point]:
        m = self.m
        a = J if u is None else m.side(v, u)
        b = J if w is None else m.side(v, w)
        return m.piece_path(v, a, b, plain=v in self.plain)

    def _bc(self, v: int, u: int | None, w: int | None) -> int:
        m = self.m
        a = J if u is None else m.side(v, u)
        b = J if w is None else m.side(v, w)
        if v in self.plain:
            return m.pieces.plain(a, b)[0]
        return m.piece_length(v, a, b)

    def _link(self, u: int, v: int) -> list[list[Point]]:
        if self.m.ec(u, v) == 0:
            return []
        return [_jump(self.m.center(u), self.m.center(v))]

    def _units(self, tour: list[int]) -> list[list[Point]]:
        n = len(tour)
        if n == 1:
            return [self._piece(tour[0], None, None)]
        units = []
        for i, v in enumerate(tour):
            w = tour[(i + 1) % n]
            units.append(self._piece(v, tour[i - 1], w))
            units.extend(self._link(v, w))
        return units

    def cost(self, tour: list[int]) -> int:
        n = len(tour)
        if n == 1:
            return self._bc(tour[0], None, None)
        return sum(
            self._bc(v, tour[i - 1], tour[(i + 1) % n]) + self.m.ec(v, tour[(i + 1) % n])
            for i, v in enumerate(tour)
        )

    def _swap(self, old: list[list[Point]], new: list[list[Point]]) -> bool:
        windows = [self.cov.add(path, -1) for path in old]
        for path in new:
            self.cov.add(path, +1)
        if self.cov.covered(windows):
            return True
        for path in new:
            self.cov.add(path, -1)
        for path in old:
            self.cov.add(path, +1)
        return False

    def _try_remove(self, v: int) -> bool:
        index = self.owner[v]
        if self.size[index] < 4:
            return False
        u, w = self.prv[v], self.nxt[v]
        uu, ww = self.prv[u], self.nxt[w]
        m = self.m
        before = (
            self._bc(u, uu, v) + self._bc(v, u, w) + self._bc(w, v, ww)
            + m.ec(u, v) + m.ec(v, w)
        )
        after = self._bc(u, uu, w) + self._bc(w, u, ww) + m.ec(u, w)
        if after >= before:
            return False
        old = [self._piece(u, uu, v), self._piece(v, u, w), self._piece(w, v, ww)]
        old += self._link(u, v) + self._link(v, w)
        new = [self._piece(u, uu, w), self._piece(w, u, ww)] + self._link(u, w)
        if not self._swap(old, new):
            return False
        self.nxt[u], self.prv[w] = w, u
        del self.nxt[v], self.prv[v], self.owner[v]
        self.size[index] -= 1
        return True

    def _try_plain(self, v: int) -> bool:
        if v in self.plain:
            return False
        single = self.size[self.owner[v]] == 1
        u = None if single else self.prv[v]
        w = None if single else self.nxt[v]
        before = self._bc(v, u, w)
        old = [self._piece(v, u, w)]
        self.plain.add(v)
        if self._bc(v, u, w) >= before or not self._swap(old, [self._piece(v, u, w)]):
            self.plain.discard(v)
            return False
        return True

    def run(self, deadline: float, rng: random.Random) -> None:
        # The longest tour first: only its length counts.
        tours = sorted(self.tours(), key=lambda tour: -self.cost(tour))
        for tour in tours:
            improved = True
            while improved and time.perf_counter() < deadline:
                improved = False
                for v in rng.sample(tour, len(tour)):
                    if time.perf_counter() >= deadline:
                        break
                    if v in self.owner and (self._try_remove(v) or self._try_plain(v)):
                        improved = True
                tour = [v for v in tour if v in self.owner]

    def waypoints(self, tour: list[int]) -> list[Point]:
        """The tour as lattice points joined by axis-parallel moves."""
        path: list[Point] = []
        for unit in self._units(tour):
            if path and path[-1] != unit[0]:
                path.extend(_jump(path[-1], unit[0])[1:])
            path.extend(unit if not path or path[-1] != unit[0] else unit[1:])
        if len(path) > 1 and path[-1] != path[0]:
            path.extend(_jump(path[-1], path[0])[1:])
        return path


# -- the solver ------------------------------------------------------------


def _block_sizes(cutter: CellSet) -> list[int]:
    """From the largest square inside the cutter up to its narrow width."""
    mask = cutter.mask
    height, width = mask.shape
    inside = 1
    for size in range(1, min(height, width) + 1):
        if any(
            mask[y : y + size, x : x + size].all()
            for y in range(height - size + 1)
            for x in range(width - size + 1)
        ):
            inside = size
    return list(range(inside, min(height, width) + 1))


def _pipeline(model: _Model, region, offsets, k, deadline, rng, warm=None):
    """Steps A to C, the k tours and the pruning, for one block model.

    `warm` is a single tour from an earlier call on the same model; the
    search then goes on from it instead of starting over. Returns the paths,
    the meta data and the single tour.
    """
    start = time.perf_counter()
    budget = deadline - start

    def at(fraction: float) -> float:
        return start + fraction * budget

    seed_rng(rng.randrange(1 << 30))

    if warm is None:
        # Step A from three starts, step C (local search) on each; keep the best.
        starts = {
            "warnsdorff": model.initial_order(),
            "rows": model.strip_order(horizontal=True),
            "columns": model.strip_order(horizontal=False),
        }
        initial = {name: model.cost(order) for name, order in starts.items()}
        best = None
        # The cheapest start nearly always stays the cheapest, so it goes first;
        # the others only run while there is time.
        for i, name in enumerate(sorted(starts, key=initial.__getitem__)):
            if i and time.perf_counter() >= at(0.25):
                break
            ring = model.tour(starts[name])
            ring.optimize()
            cost = ring.cost()
            if best is None or cost < best[0]:
                best = (cost, name, ring.order())
        _, chosen, order = best
    else:
        initial, chosen, order = {}, "warm", list(warm)
    order = _lns(model, order, at(0.5), rng)
    single = model.cost(order)

    # k tours: split, then take turns balancing and improving the longest.
    tours = _split(model, order, k)
    for i, tour in enumerate(tours):
        part = model.tour(tour)
        part.optimize()
        tours[i] = part.order()
    while time.perf_counter() < at(0.85):
        if len(tours) > 1:
            tours = _balance(model, tours, at(0.85))
        longest = max(range(len(tours)), key=lambda i: model.cost(tours[i]))
        until = min(at(0.85), time.perf_counter() + max(0.5, 0.05 * budget))
        tours[longest] = _lns(model, tours[longest], until, rng)

    pruner = _Pruner(model, tours, _Coverage(region, offsets))
    pruner.run(deadline, rng)
    final = pruner.tours()
    paths = [pruner.waypoints(tour) for tour in final]
    meta = {
        "block_size": model.s,
        "blocks": model.n,
        "initial_tours": initial,
        "start": chosen,
        "single_tour": single,
        "tour_blocks": [len(t) for t in final],
    }
    return paths, meta, order


def _repair(validator: SolutionValidator, instance, paths, offsets) -> list[list[Point]]:
    """Safety net: send the shortest tour to any cell still left uncovered."""
    solution = _as_solution(instance, paths, {})
    uncovered = list(validator.uncovered_cells(solution).cells())
    dx, dy = offsets[0]
    for cell in uncovered:
        target = (cell[0] - dx, cell[1] - dy)
        shortest = min(range(len(paths)), key=lambda i: _length(paths[i]))
        path = paths[shortest]
        at = min(range(len(path)), key=lambda i: _l1(path[i], target))
        detour = _jump(path[at], target) + _jump(target, path[at])[1:]
        paths[shortest] = path[:at] + detour + path[at + 1 :]
    return paths


def _length(path: list[Point]) -> int:
    return sum(_l1(path[i], path[(i + 1) % len(path)]) for i in range(len(path)))


def _as_solution(instance, paths, meta) -> CGSHOP2027Solution:
    k = instance.number_of_cutters
    tours = [make_tour(path) for path in paths]
    park = paths[0][0] if paths and paths[0] else (0, 0)
    tours.extend(make_tour([park]) for _ in range(k - len(tours)))
    return CGSHOP2027Solution(instance_uid=instance.instance_uid, tours=tours, meta=meta)


def _refine(region, offsets, paths, deadline, rng) -> list[list[Point]]:
    """Shorten the tours with the exact-coverage local search of `refine`."""
    refiner = Refiner(region.mask, region.origin, offsets, paths)
    refiner.run(deadline, rng)
    return refiner.paths()


_warm = False


def _warm_up(offsets: list[Point], s: int) -> None:
    """Run every compiled kernel once on a tiny square, outside the clock.

    The first call of a kernel compiles it, or loads it from numba's cache.
    Doing that here keeps compile time out of the time limit.
    """
    global _warm
    if _warm:
        return
    side = 4 * s
    square = CellSet(np.ones((side, side), dtype=bool), (0, 0))
    model = _Model(square, offsets, s)
    rng = random.Random(0)
    paths, _, _ = _pipeline(model, square, offsets, 1, time.perf_counter() + 0.05, rng)
    _refine(square, offsets, paths, time.perf_counter() + 0.05, rng)
    _warm = True


def solve(
    instance: CGSHOP2027Instance, time_limit: float = 30.0, seed: int = 0, refine: bool = True
) -> CGSHOP2027Solution:
    """Tile-based mowing (TSP_Cov + turn cost), best over the block sizes.

    `time_limit` is in seconds and is shared among the block sizes.
    """
    region = region_cells(instance)
    cutter = cutter_cells(instance)
    offsets = list(cutter.cells())
    _warm_up(offsets, _block_sizes(cutter)[-1])
    began = time.perf_counter()
    k = instance.number_of_cutters
    validator = SolutionValidator(instance)
    rng = random.Random(seed)

    if len(region) == 0:
        return _as_solution(instance, [], {"algorithm": "fekete"})

    def attempt(model: _Model, deadline: float, warm=None):
        """One run of the pipeline, repaired if needed, then refined."""
        share = deadline - time.perf_counter()
        paths, meta, order = _pipeline(
            model, region, offsets, k, deadline - REFINE_SHARE * share, rng, warm
        )
        solution = _as_solution(instance, paths, meta)
        if validator.check_for_errors(solution):
            paths = _repair(validator, instance, paths, offsets)
            meta["repaired"] = True
            solution = _as_solution(instance, paths, meta)
        if refine:
            refined = _refine(region, offsets, paths, deadline, rng)
            candidate = _as_solution(instance, refined, meta)
            if not validator.check_for_errors(candidate):
                meta["unrefined"] = solution.max_tour_length
                solution = candidate
        return solution, meta, order

    # Every block size gets a short race; the winner gets the rest of the
    # time and goes on from its race tour. The largest blocks (TSP_Cov) win
    # most often, as in the paper, but not always.
    sizes = _block_sizes(cutter)[::-1]
    race = RACE_SHARE / len(sizes) if len(sizes) > 1 else 1.0
    best, results = None, {}
    for i, s in enumerate(sizes):
        model = _Model(region, offsets, s)
        solution, meta, order = attempt(model, began + time_limit * race * (i + 1))
        results[s] = (solution.max_tour_length, model, order)
        if best is None or solution.max_tour_length < best[0].max_tour_length:
            best = (solution, meta)
    if len(sizes) > 1:
        _, model, order = min(results.values(), key=lambda r: r[0])
        solution, meta, _ = attempt(model, began + time_limit, warm=order)
        if solution.max_tour_length < best[0].max_tour_length:
            best = (solution, meta)

    solution, meta = best
    meta = {
        "algorithm": "fekete",
        **meta,
        "sizes_tried": sizes,
        "seconds": round(time.perf_counter() - began, 1),
    }
    return solution.model_copy(update={"meta": meta})
