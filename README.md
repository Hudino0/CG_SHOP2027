# CG:SHOP 2027 — pipeline

Workspace for the Ninth Computational Geometry Challenge,
**Multi-Robot Lawn Mowing for Polyominoes**
([competition page](https://cgshop.ibr.cs.tu-bs.de/competition/cg-shop-2027/)).

Everything is built on top of the organizers' own
[`cgshop2027-pyutils`](https://github.com/CG-SHOP/pyutils27), so parsing,
verification and drawing match exactly what the upload verifier does.

## The problem in one paragraph

Given a polyomino region `R` (the lawn), a polyomino cutter `C` with a
designated center, and a swarm size `k`, find `k` **closed rectilinear
trajectories with integer turning points** such that every point of `R` is
covered by the cutter at some position along some trajectory. Trajectories may
leave `R` freely and may cross each other. **The objective is the length of the
longest trajectory, to be minimized.**

Scoring per instance is `B(I)² / B_G(I)²` — the square of the ratio between the
best objective anyone submitted and yours — summed over all instances. Halving
your tour length is worth four times as much as it looks.

### The one fact that shapes every algorithm

The verifier does *not* walk the tours cell by cell. It collects the set `A` of
all lattice points any cutter ever stands on, and checks

```
R ⊆ dilate(A, C)        # Minkowski sum of the anchor set with the cutter
```

Continuous motion adds nothing beyond the lattice points, because for unit
cells `C ⊕ [p, p+e] = (C+p) ∪ (C+p+e)`. So coverage is a **pure set-cover
question over anchor points**, and revisiting a point is free. Anything you
design can be checked against that model directly.

## Layout

```
data/raw/           downloaded archives
data/instances/     *.instance.json
data/solutions/<run>/   *.solution.json — one directory per solver run
out/catalog.csv     one row per instance, all the size numbers
out/verdicts.json   feasibility + objective + gap, per run
out/gallery.html    the browser (open it, or serve out/ over http)
out/renders/        PNGs, out/animations/ GIFs
src/cgshop27/       the pipeline package
```

## Setup

```bash
python -m venv .venv && .venv/Scripts/python -m pip install -e .
```

## Usage

```bash
cg27 fetch                          # download + unpack the example instances
cg27 index -j 8                     # build out/catalog.{csv,json}
cg27 solve -j 8 --run baseline      # write data/solutions/baseline/
cg27 verify --score                 # feasibility, gap to lower bound, scores
cg27 render -j 8                    # PNGs of the instances
cg27 render -j 8 --run baseline     # PNGs of a run's solutions
cg27 gallery --open                 # out/gallery.html
cg27 animate iso_11k_6k_3p --run baseline
cg27 submit --run baseline          # out/submission_baseline.zip
```

`--filter` (substring on the file name) and `--limit` narrow any stage, which is
how you iterate quickly:

```bash
cg27 solve --filter fpg73_1k --run experiment && cg27 verify --run experiment
```

`cg27 verify` with several `--run` flags scores them against each other using
the competition formula, with the best local objective standing in for the best
submitted one — the fastest way to tell whether a change actually helped.

The gallery serves fine from `file://`, but a few browsers block the relative
image loads; if the thumbnails are blank, serve the directory instead:

```bash
.venv/Scripts/python -m http.server 8731 --directory out
```

## What the catalog gives you

Per instance: region area in cells, connected components, bounding box and how
densely it is filled, vertex and hole counts, the cutter's footprint and its
widest cross-section, and `lower_bound`.

`lower_bound` is a valid lower bound on the objective: one unit of travel sweeps
at most `cross` new cells, so `area ≤ k · (cutter_area + L · cross)` for the
longest tour `L`. It is weak on sparse regions — it ignores all travel between
disconnected parts — but it is cheap, always valid, and makes runs comparable
across instances of wildly different sizes.

## The baseline solver

`boustrophedon` cuts the region into horizontal bands as tall as the cutter's
longest run of consecutive occupied rows, clips each band to the columns that
actually contain region cells, splits the band list into `k` contiguous groups
balanced by estimated cost, and serpentines each group. It is feasible by
construction and lands around **2.2× the area lower bound** on the example set
(75/75 feasible).

It is a reference point, not a contender. The obvious places to beat it:

- **Bands ignore shape.** A band spanning a region that is two thin arms with a
  gap pays full width for both. Splitting bands into runs and routing between
  them is a TSP-with-coverage problem.
- **The split is contiguous.** Cutters get horizontal slabs; for a region that
  is naturally two blobs, a non-contiguous assignment is much better.
- **No reduction to set cover.** Given the anchor-set model above, computing a
  small covering anchor set first and then routing it (the approach in Fekete
  et al., ALENEX 2023 / ESA 2023) is the direction the literature points.

## Adding a solver

Write `src/cgshop27/solvers/<name>.py` exposing
`solve(instance) -> CGSHOP2027Solution`, register it in
`solvers/__init__.py::SOLVERS`, then:

```bash
cg27 solve --solver <name> --run <name> -j 8 && cg27 verify --score
```

`cg27 solve` verifies before writing, so an infeasible solution never reaches
`data/solutions/` and never lands in a submission zip.

## Timeline

- Test instances and pyutils: released (2026-08-25)
- Contest instances: 2026-10-15
- Contest closes: 2027-01-31 (AoE)

Only feasible solutions count, and ties break on submission time — submit early
and often.
