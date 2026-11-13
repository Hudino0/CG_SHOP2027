# CG:SHOP 2027 — pipeline

Tools to download, draw, solve and check the instances of the Ninth
Computational Geometry Challenge. The problem is **Multi-Robot Lawn Mowing for
Polyominoes**.

- Competition page: <https://cgshop.ibr.cs.tu-bs.de/competition/cg-shop-2027/>
- Official Python package: <https://github.com/CG-SHOP/pyutils27>

This project uses the official package. Therefore the reader, the verifier and
the plots agree with the verifier of the upload site.

---

## Quick start

Start here if the machine has nothing on it. You need **Python 3.11 or later**
and **Git**. Nothing else.

**Step 1. Install.** Do this one time.

```powershell
git clone https://github.com/Hudino0/CG_SHOP2027.git
cd CG_SHOP2027
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
```

On Linux or macOS, replace line 4 with `source .venv/bin/activate`.

Activate the environment again in each new terminal. Then the command `cg27`
works everywhere in the project.

**Step 2. Get the instances.**

```bash
cg27 fetch
```

The repository already carries the instances, so this step is optional. It
refreshes them from the organizers: 75 test instances into `instances/test/`
(they do not score) and 250 official contest instances (v0, 14 October 2026)
into `instances/competition/`. Use `--suite test` or `--suite competition` for
one set. The gallery shows a badge and a filter that tell the two sets apart.

**Step 3. Solve one instance and watch the solution.**

```bash
cg27 solve --filter iso_11k_6k_3p --run baseline
cg27 animate iso_11k_6k_3p --run baseline --open
```

Your browser opens an HTML page. Press play. The three cutters move along their
tours. The green area behind them is the part of the region that they covered.

**Step 4. Do the same for all 75 instances.**

```bash
cg27 index -j 8
cg27 solve -j 8 --run baseline
cg27 verify --run baseline
cg27 render -j 8
cg27 render -j 8 --run baseline
cg27 gallery
```

Then start a small server and open <http://localhost:8731/gallery.html>:

```bash
python -m http.server 8731 --directory out
```

### How long each step takes

These times come from a clean clone on Windows, with 8 workers:

| Step | Time |
|---|---|
| `git clone` | 1 s |
| `python -m venv` and `pip install -e .` | 32 s |
| `cg27 fetch` | 3 s |
| `cg27 index -j 8` | 5 s |
| `cg27 solve -j 8` (75 instances) | 4 s |
| `cg27 verify` | 6 s |
| `cg27 render -j 8` | 14 s |
| `cg27 render -j 8 --run baseline` | 14 s |
| `cg27 gallery` | 6 s |
| `cg27 animate` (one instance, 80 frames) | 21 s |

The 75 test instances use 2.4 MB. The 250 competition instances use 8.9 MB.

### Which viewer to use

| You want to see | Use | Needs a server |
|---|---|---|
| One route, over time | `cg27 animate` | No. The page holds every frame. |
| All instances, side by side | `cg27 gallery` | Yes. The images sit in other files. |

The animation page loads the icons of its buttons from the internet. Without a
connection the icons disappear, but the buttons still work.

---

## 1. The problem

You get three things:

- A **region** `R`. It is a polyomino. It can have holes.
- A **cutter** `C`. It is a small polyomino. It has one center point.
- A number `k`. It is the number of cutters.

You must find `k` **tours**. A tour is the path of the center of one cutter.

These rules apply:

- A tour must be closed. The cutter must return to its start point.
- Each move must be horizontal or vertical.
- Each corner point must have integer coordinates.
- The `k` cutters together must cover all of `R`.
- A tour can go outside `R`. This is permitted.

The **objective** is the length of the longest tour. Make this length small.

### The score

For each instance the site computes `B² / B_G²`.

- `B` is the best objective of all teams.
- `B_G` is your objective.

The site adds these values over all instances. Note the square: if you divide
your tour length by 2, your score for that instance increases by 4.

---

## 2. How the verifier thinks

Read this section before you write an algorithm. It changes the shape of the
problem.

The verifier does not follow the tours step by step. It does two operations:

1. It collects the set `A`. This set contains all integer points where a cutter
   stops or passes.
2. It tests `R ⊆ dilate(A, C)`.

`dilate(A, C)` is the Minkowski sum. It puts one copy of the cutter on each
point of `A`.

Continuous movement adds nothing to the coverage. For unit cells the rule
`C ⊕ [p, p+e] = (C+p) ∪ (C+p+e)` applies.

Two results follow:

- Coverage is a **set cover problem on integer points**. It is not a path
  problem.
- A second visit to the same point costs nothing for coverage.

You can test any idea against this model directly.

---

## 3. What is in this repository

| File | Function |
|---|---|
| `pyproject.toml` | Declares the package and the `cg27` command. |
| `src/cgshop27/config.py` | Holds all paths and the download URL. |
| `src/cgshop27/catalog.py` | Reads instances. Computes the size numbers and a lower bound. |
| `src/cgshop27/evaluate.py` | Checks solutions. Compares runs. Makes the upload file. |
| `src/cgshop27/render.py` | Writes PNG images and animations (HTML or GIF). |
| `src/cgshop27/gallery.py` | Writes one HTML page to browse all instances. |
| `src/cgshop27/solvers/boustrophedon.py` | The baseline solver. |
| `src/cgshop27/solvers/fekete.py` | The solver of Fekete et al. (2023). See 5.5. |
| `src/cgshop27/solvers/_blockls.py` | The compiled parts of `fekete`: puzzle pieces, 2-opt, Or-opt and LNS. |
| `src/cgshop27/solvers/refine.py` | Shortens finished tours cell by cell. See 5.6. |
| `src/cgshop27/solvers/_tour.py` | Converts waypoints into tours that the schema accepts. |
| `src/cgshop27/solvers/scale.py` | Solves on the coarse lattice of an instance and lifts the tours. See 5.7. |
| `src/cgshop27/solvers/lanes.py` | The strip solver: no blocks, any cutter width. See 5.8. |
| `src/cgshop27/solvers/anchors.py` | The cover-first solver. See 5.13. |
| `src/cgshop27/bounds.py` | The weighted area bound (a lower bound from a linear program). See 5.14. |
| `results/` | The measured results: the table for each instance, the bounds and the upload file. In git. |
| `docs/algoritmo.md` | The statement, the proofs of feasibility and the lower bounds. |
| `src/cgshop27/overlap.py` | Measures how much of the region two or more tours sweep. |
| `src/cgshop27/gridgraph.py` | Draws the block grid graph of the `fekete` solver. |
| `src/cgshop27/pipeline.py` | Solves, verifies and draws the grid graph for several solvers. Writes the report. |
| `docs/PROMPT_FABLE.md` | The prompt for a long, rigorous solver session. |
| `docs/revision_sistematica_literatura.pdf` | The literature review. It assumes a 1x1 cutter; the real cutters differ. |
| `src/cgshop27/cli.py` | The `cg27` command and its 17 sub-commands. |

The pipeline writes into these directories. Git ignores them, except `instances/`.

| Directory | Content |
|---|---|
| `instances/test/`, `instances/competition/` | The instance files. They are in git. |
| `data/solutions/<run>/` | The solution files. One directory for each run. |
| `out/catalog.csv` | One line for each instance, with all size numbers. |
| `out/verdicts.json` | Result, objective and gap for each solution. |
| `out/overlap.json` | The overlap between the tours, for each solution. |
| `out/gallery.html` | The HTML page to browse the instances. |
| `out/renders/` | The PNG images. |
| `out/animations/` | The animations. |
| `out/grids/` | The grid graph images. |

A **run** is one directory of solutions. It is normally the output of one
solver. Use one run for each experiment.

---

## 4. How to run it

The **Quick start** above gives the shortest path. This section explains each
command and the options that matter.

The full pipeline:

```bash
cg27 fetch                          # download the example instances
cg27 index -j 8                     # write out/catalog.csv
cg27 solve -j 8 --run baseline      # write data/solutions/baseline/
cg27 verify --score                 # check the solutions and score them
cg27 render -j 8                    # draw the instances
cg27 render -j 8 --run baseline     # draw the solutions of one run
cg27 gallery --open                 # write and open out/gallery.html
cg27 animate iso_11k_6k_3p --run baseline --open   # watch the tours
cg27 overlap -j 8 --run baseline    # how much the tours overlap
cg27 grid iso_11k_6k_3p --run fekete --open      # the grid graph
cg27 submit --run baseline          # write out/submission_baseline.zip
```

### Make the upload file for the contest (one command)

```bash
cg27 campaign -j 4 --time-limit 30 --seed 0
```

This command does the whole chain on the 250 contest instances:

1. `cg27 index` writes the catalog.
2. `cg27 solve` runs `boustrophedon`, and then `anchors`, `fekete` and
   `lanes`. Each instance runs in its own process with a memory limit. The
   time limit grows with the instance size, from `--time-limit` to
   `--time-max`.
3. `cg27 polish` refines each run. A result that is better than the stored
   one goes into the run `best`. This run **only improves**: a longer solution
   never replaces a shorter one. The result of the coarse stage goes into
   `best_coarse`, for later polish runs.
4. `cg27 submit --run best --check competition` writes
   `out/submission_best.zip`, reads it again and runs the official verifier.
5. `cg27 report` writes `out/results.csv`: lower bound, objective, gap, time
   and memory for each instance and each run.

Then spend the remaining time on the search that still finds gains:

```bash
cg27 polish -j 4 --run best_coarse --into best --coarse-into best_coarse \
     --time-limit 60 --time-max 600 --seed 1
cg27 grind --rounds 3 --first 1
```

Run them again with another `--seed`. The seeds are fixed, but the solvers
stop on a time limit. Thus a faster machine can get a slightly better result.

### Run all solvers and see the grid graph (one command)

The command `cg27 pipeline` does the whole chain for each instance and each
solver: it solves, verifies, and draws the grid graph with the tours on top.
Then it writes one HTML page that puts the solvers side by side.

```bash
cg27 pipeline -j 8                                # all solvers, all instances
cg27 pipeline --filter iso_11k_6k_3p --open       # one instance, open the report
cg27 pipeline --solver fekete --time-limit 60     # one solver
```

| Option | Meaning |
|---|---|
| `--solver` | A solver to run. Repeat it for more. Default: all of them. |
| `--prefix` | The runs are named `<prefix>_<solver>`. Default prefix: `pipe`. |
| `--time-limit` | Seconds for each instance, for the solvers that accept it. |
| `--clean` | Empty the runs first. |

The command writes `out/pipeline/index.html` (the report),
`out/pipeline/summary.json` (objective, gap, time, nodes and edges for each
pair) and the images in `out/grids/<prefix>_<solver>/`. An infeasible solution
is not saved. The exit code is 1 if one solution is infeasible. The runs also
work with `verify`, `animate` and `submit`.

### Measure the overlap between the tours

The command `cg27 overlap` looks at each tour on its own. It finds the region
cells that the tour sweeps. Then it compares the tours:

```bash
cg27 overlap -j 8 --run fekete --run baseline
```

| Column | Meaning |
|---|---|
| `shared_%` | The part of the region that two or more tours sweep. |
| `pairs_%` | The part of the region that both tours of a pair sweep. |
| `own_shared_%` | For each tour: the part of its own cells that another tour also sweeps. |

The command writes all values to `out/overlap.json`. Instances with one cutter
have no overlap.

Overlap is not always waste. The score uses only the longest tour. Overlap on
a short tour costs nothing. On the 75 examples, `baseline` has no overlap: its
bands do not touch. `fekete` has a median of 1.4 % and a maximum of 8.2 %.
The overlap is at the borders between the zones of two cutters, and where one
cutter crosses the zone of another cutter.

### See the grid graph

The `fekete` solver does not look at single cells. It cuts the region into
blocks of `s x s` cells. Each block that holds region cells is a node. Two
nodes have an edge when their blocks share a side. Step A of the solver finds a
round trip on this graph.

```bash
cg27 grid iso_11k_6k_3p --run fekete --open
```

| In the image | Meaning |
|---|---|
| Green cells | The region. |
| Thin grid | The blocks, at the offset with the fewest blocks. |
| White node | A block that the region fills completely. |
| Yellow node | A block that the region fills only in part. |
| Black line | An edge of the grid graph. |
| Colored lines | The tours of the run, one color for each cutter. |

With `--run`, the block size comes from the solution. Without it, the command
uses the cutter width, or the value of `--block`. The image goes to
`out/grids/<run>/`.

### Watch the tours over time

The command `cg27 animate` shows the cutters as they move. It reads a run from
`data/solutions/`. Therefore it works for **every** solver you write, not only
for the baseline. You do not need to change it.

There are two formats:

| Format | Use it for |
|---|---|
| `--format html` | Study one route. It has play, pause, step, speed and a time slider. |
| `--format gif` | Share the result. One file, but no controls. |

```bash
cg27 animate iso_11k_6k_3p --run baseline --format html --open
cg27 animate iso_11k_6k_3p --run baseline --format gif
cg27 animate --filter iso_ --limit 5 --run baseline   # a batch
```

The animation shows two things at the same time:

- Where each cutter is now. Each cutter has its own colour.
- Which cells the cutters already covered. This area is green and it grows.

Use the animation to find errors. If a solver leaves a hole, you see **when**
the cutters passed near it and **why** they missed it.

Two limits to know:

- All cutters move at one unit for each step. The animation stops when the
  longest tour ends.
- `--frames` sets the number of frames. A long tour in few frames jumps a large
  distance between frames. The green area stays exact, because the code stamps
  every position in between. Choose small instances, or raise `--frames`.

An HTML file of 120 frames is near 8 MB. Do not commit these files.

Use `--filter` and `--limit` to work on few instances. This makes each test
fast:

```bash
cg27 solve --filter fpg73_1k --run test
cg27 verify --run test
```

Give `--run` two or more times to compare experiments. The command uses the
score formula of the competition. The best local objective replaces `B`:

```bash
cg27 verify --run baseline --run test
```

This comparison is the fastest way to see if a change helps.

The gallery opens from a `file://` address. Some browsers block the images
there. If the images are empty, start a small server:

```bash
.venv/Scripts/python -m http.server 8731 --directory out
```

---

## 5. What I did

### 5.1 The catalog

For each instance the catalog computes these values:

- The area in cells.
- The number of connected parts.
- The bounding box and how full it is.
- The number of vertices and the number of holes.
- The shape of the cutter and its widest row or column.
- A lower bound on the objective.

The **lower bound** is a limit that no solution can pass. One unit of movement
covers `cross` new cells at a maximum. The value `cross` is the widest row or
column of the cutter. Therefore `area ≤ k · (cutter_area + L · cross)`, where
`L` is the longest tour.

The bound is weak on regions with separate parts, because it ignores the travel
between them. But the bound is always correct and it is fast. It lets you
compare instances of very different sizes.

### 5.2 The baseline solver

The solver `boustrophedon` does four steps:

1. It cuts the region into horizontal bands. The height of a band is the
   longest run of full rows of the cutter.
2. It cuts each band at the first and the last column that contain region
   cells.
3. It divides the list of bands into `k` groups of equal cost.
4. It moves each cutter through its bands in a zig-zag path.

The solver is correct by construction. The docstring gives the proof.

Result on the 75 example instances:

| Measure | Value |
|---|---|
| Valid solutions | 75 of 75 |
| Gap to the lower bound (median) | 2.19 × |
| Gap to the lower bound (minimum) | 1.16 × |
| Gap to the lower bound (maximum) | 4.31 × |

### 5.3 One error that I found and corrected

The first version made tours that the verifier refused. The cause was in
`_tour.py`. The code removed points on a straight line, because such points are
normally not necessary. But a zig-zag path has turn points: the cutter goes to
the right, then it stops and goes to the left. The three points are on one
line, but the middle point is the end of the movement.

The code removed these turn points. The sweep became shorter. Some columns
stayed open.

The correction is small: remove a point only if it lies **between** its two
neighbours.

### 5.4 The safety rule in the pipeline

The command `cg27 solve` checks a solution before it writes the file. An
invalid solution never enters `data/solutions/`. Therefore an invalid solution
can never enter an upload file.

---

### 5.5 The solver of Fekete et al.

The solver `fekete` uses the method of this paper:

> S. P. Fekete, D. Krupke, M. Perk, C. Rieck, C. Scheffer. *The Lawn Mowing
> Problem: From Algebra to Algorithms.* ESA 2023. arXiv:2307.01092.

The paper mows a polyomino with a disk. The cutters of this contest are
discrete disks: squares (`s`), diamonds (`l`), rounded squares (`p`, `d`, `c`).
Thus the method applies almost directly.

The solver does these steps:

1. **Blocks.** It cuts the region into square blocks of side `s`. A block is a
   "pixel" of the paper. It uses the grid offset that gives the fewest blocks
   (paper, 5.1.1).
2. **Puzzle pieces.** A piece is the shortest path through a block, from one
   side to another side, that covers the block. A straight piece costs `s`. A
   turn or a U-turn costs more: this is the **turn cost**. The paper derives the
   pieces by hand for a disk. The solver computes them for any cutter: it tries
   paths with 0, 1 and 2 corner points, shortest first. It also computes pieces
   for blocks at the border, which contain only part of the region.
3. **Tour on the blocks** (paper, step A). It makes three start tours: a
   Warnsdorff walk, a tour along rows and a tour along columns. It keeps the
   best one.
4. **Improve the tour** (paper, step C, "TSP_Turn"). 2-opt and Or-opt moves
   use the true cost, turn cost included. Then a large neighbourhood search
   removes the blocks in a small window and puts them back (paper, 5.1.4).
5. **k tours.** It cuts the tour into `k` closed tours of equal cost. Then it
   moves blocks from the longest tour into its neighbours, and improves the
   longest tour again.
6. **Prune.** It checks the exact coverage. It removes a block visit, or it
   replaces a covering piece by a plain path, if the neighbours already cover
   the cells.
7. **Refine.** It leaves the blocks and shortens the tours cell by cell. See
   5.6.

The block side `s` goes from the largest square inside the cutter (the
"TSP_Small" of the paper) to the width of the cutter ("TSP_Cov"). Each size
gets a short race (35 % of the time in total). The best size gets the rest of
the time and continues from its race tour. The largest size wins in most
cases. This agrees with the paper.

Three differences from the paper:

- The paper uses Concorde for step A and Gurobi for step C. This solver uses
  Python, NumPy and numba. The local search and the LNS replace the integer
  program.
- The paper makes one tour. This solver makes `k` tours and makes the longest
  one short.
- Step 7 is not in the paper.

The puzzle pieces and the local search run as compiled code (numba). The
first run compiles them and keeps them in a cache. This takes approximately
30 s one time. The time limit does not include it.

Run it with a time limit for each instance. The default is 30 s:

```bash
cg27 solve -j 8 --solver fekete --run fekete --time-limit 20
cg27 verify --run baseline --run fekete
```

Result on the 75 example instances, with 20 s for each instance and 8 workers
(approximately 3.5 min in total). The column "first version" is the solver
before the changes of 5.6:

| Measure | `boustrophedon` | `fekete`, first version | `fekete` |
|---|---|---|---|
| Valid solutions | 75 of 75 | 75 of 75 | 75 of 75 |
| Gap to the lower bound (median) | 2.19 × | 1.64 × | 1.55 × |
| Gap to the lower bound (minimum) | 1.16 × | 1.12 × | 1.07 × |
| Gap to the lower bound (maximum) | 4.31 × | 3.00 × | 2.68 × |
| Local score (75 is the maximum) | 41.6 | 64.9 | 75.0 |

The longest tour of `fekete` is 28 % shorter than the baseline (median). The
changes of 5.6 make it 7 % shorter again (median, maximum 18 %). It is never
longer than the first version.

### 5.6 Where the length goes, and what I changed

I measured the solutions of the first version of `fekete`. These are the
results (medians over the 75 instances):

| Measurement | Value | What it shows |
|---|---|---|
| Longest tour ÷ (single tour ÷ `k`) | 1.007 | The division between cutters costs less than 1 %. |
| Swept cells outside the region | 34 % | Most of the loss is at the border and at the holes. |
| Tour length ÷ distinct points | 1.04 | Second visits cost only 4 %. |
| Block area ÷ region area | 1.40 | Border blocks are almost empty, but a pass costs `s`. |
| Block tour ÷ (blocks × `s`) | 1.08 | The block tour itself is close to its ideal. |

Thus a better division of the region between the cutters (for example with a
quadtree) cannot give much. The loss is in the border blocks and in the time
that the search needs.

I made three changes:

1. **Refine the tours cell by cell** (`refine.py`). The verifier looks at
   lattice points, not at blocks. The refiner expands each tour into its unit
   steps and counts, for each cell, how many steps of all tours sweep it. Then
   it applies two moves. Each move keeps every region cell swept:
   - *Shortcut*: remove a part of a tour and join its ends with an L, if other
     steps sweep all its cells.
   - *Reroute*: replace a part between two corners with the shortest path with
     three corners or fewer that sweeps the cells that only this part swept.
     This moves a lane or a U-turn toward the border.

   Gain: 3.4 % (median), maximum 21 %. It needs less than 1 s.
2. **Compile the block search** (`_blockls.py`). The 2-opt, Or-opt and LNS
   moves are the same as before. The piece lengths are computed before the
   search starts, with bit masks. All results are equal to the Python code. The
   search is approximately 100 times faster: 20 s now give better tours than
   300 s gave before.
3. **Race the block sizes.** See 5.5.

These experiments did not help, and the solver does not use them:

- Longer reroutes (6 or 8 segments instead of 4): no gain.
- Grid offsets other than the offset with the fewest blocks: ±1 % to 2 %, no
  clear winner.
- Blocks that start at the border of each vertical strip: only 6 % fewer
  blocks before the cost of the steps between strips.

Sources:

- S. P. Fekete, D. Krupke, M. Perk, C. Rieck, C. Scheffer. *The Lawn Mowing
  Problem: From Algebra to Algorithms.* ESA 2023. arXiv:2307.01092. Section
  5.3: step C gives approximately 5 % on polyominoes. The IP gap stays below
  7 %.
- D. Krupke. *Near-Optimal Coverage Path Planning with Turn Costs.* ALENEX
  2024. arXiv:2310.20340.
- J. Tang, H. Ma. *Large-Scale Multi-Robot Coverage Path Planning via Local
  Search.* AAAI 2024. arXiv:2312.10797.

### 5.7 The coarse lattice

All coordinates of a contest instance are multiples of a pitch `g`: 1, 2 or 6
for 1, 2 or 3 cutters. `scale.py` divides the instance by `g`, solves it, and
multiplies the tours by `g`. The module gives the proof that the result is
valid. The instance becomes `g x g` times smaller: the largest one has
1 000 137 coarse cells, not 8 748 612.

The first version of `fekete` failed on each cutter with a width of 8 cells or
more, because a block did not fit into a 64-bit mask. That was 170 of the 250
contest instances. Now `fekete` runs on the coarse lattice. If the cutter is
still wider than 7 coarse cells, the lattice becomes coarser again: the region
grows to full coarse cells and the cutter shrinks to full coarse cells. The
result stays valid, but it loses quality.

### 5.8 The solver `lanes`

The solver `lanes` has no blocks. It works for each cutter width and shape.

1. **Strips.** It cuts the rows of the region into strips. A strip is at most
   as high as the cutter. One horizontal line of the cutter center mows one
   strip. A dynamic program finds the cut with the lowest cost. It tries rows
   and columns.
2. **Lanes.** In each strip it computes the parts of the line that the center
   must visit. These parts are the lanes.
3. **Route.** A tour must pass along each lane. 2-opt and Or-opt moves and
   random kicks improve the order of the lanes until the time is over.
4. **k tours.** Two starts: each cutter gets two columns of the region (up
   one, down the other), or one tour is cut into `k` tours. Lanes move from
   the longest tour to the others.
5. **Refine.** The refiner of 5.6 shortens the tours.

`docs/algoritmo.md` gives the proof that the lanes cover the region.

Use it like the other solvers:

```bash
cg27 solve -j 4 --solver lanes --run lanes --time-limit 20
```

### 5.9 A stronger lower bound

A solution for a cutter is also a solution for each larger cutter. Therefore
a lower bound for a larger cutter is valid for the smaller one. The catalog
fills the notches of the cutter and takes the area bound of that shape. For
the X-shaped cutters this bound is up to 50 % higher than the old one. The
proof is in `docs/algoritmo.md`.

### 5.10 One more error that I found and corrected

The refiner has a test that decides if the cutter is convex. Only then it
uses the reroute move. The test read a variable of an earlier loop. The result
was `False` for each cutter that is not a rectangle, and the reroute move was
off. With the correct test, `cg27 polish` makes the tours of `fekete` 0.5 % to
2.3 % shorter on the instances that I measured.

### 5.11 The refiner, again

Three changes make the refiner stronger. `docs/algoritmo.md` gives the
reasons why each move keeps the solution valid.

- **X-shaped cutters.** The reroute move tests if a segment sweeps a cell.
  The test now uses the runs of each row and column of the cutter. It is
  exact for a cutter with notches. Before, the move was off for the 52
  contest instances with such a cutter. Measured: up to 10.6 % shorter.
- **Drift.** When no move makes a tour shorter, the refiner applies reroutes
  of equal length at random. A later move can then gain. A tour never becomes
  longer.
- **Trade between tours.** The longest tour gives a part to another tour, or
  the two tours swap parts. All points stay visited, thus the coverage cannot
  break. Measured: up to 4.8 % on the longest tour.

`cg27 polish` runs the refiner on stored solutions: first on the coarse
lattice, then on the fine lattice.

### 5.12 Many short runs

A run of 150 s is not better than a run of 30 s on a small instance. But a
different seed or a different grid offset gives a different tour: the lengths
differ by 1 % to 3 %. The command `cg27 grind` uses this:

```bash
cg27 grind --rounds 6 -j 4
```

Each round solves all instances with `fekete` (grid offset = round number)
and with `lanes` (seed = round number), polishes the round, and copies the
gains into the run `best`. The time limit grows with the instance size
(`--time-limit` to `--time-max`).

### 5.13 The solver `anchors` and the large neighbourhood search

`fekete` and `lanes` mow full blocks or full strips. At the border of the
region a block or a strip mows much ground outside the region: the best tours
of these solvers sweep 26 % more area than the region (median). A simple set
of cutter positions can do better. A greedy cover that gives a penalty to
each cell outside the region sweeps only 2 % to 7 % more.

The solver `anchors` starts from that cover:

1. It finds the cutter positions (the anchors).
2. It makes a tour through the anchors, with the router of `lanes`.
3. The refiner removes the anchors that the walk makes unnecessary.

The refiner also got a new search that uses the same idea on a finished
tour. One step: take a window on the longest tour, compute new anchors for
the region cells in the window, let the tour visit each new anchor (out and
back), and refine all parts of the tours in the window. Keep the step only if
the longest tour is shorter. `cg27 polish` and `anchors` use this search
until their time is over.

`cg27 polish --coarse-into best_coarse` also keeps the result that still lies
on the coarse lattice. A later polish continues from that result at low cost.

```bash
cg27 solve -j 4 --solver anchors --run anchors --time-limit 20 --time-max 180
cg27 polish -j 4 --run best_coarse --into best --coarse-into best_coarse \
     --time-limit 60 --time-max 600
```

### 5.14 A stronger lower bound from a linear program

The area bound gives the same weight to each region cell. The **weighted
area bound** gives each cell its own weight `u`. The rule is: no step of the
cutter can add cells with a total weight above 1. Then a tour of length `L`
sweeps a weight of at most `L` plus one stamp, and the total weight of the
region is a lower bound. The proof is in `docs/algoritmo.md` (Theorem 11).

The best weights are the solution of a linear program. Where the region is
thinner than the cutter, a step adds few region cells, and these cells get
more weight. Thus the bound is much higher for regions with fine features.

Each feasible `u` is a proof of the bound, optimal or not. For this reason a
simple first-order method is sufficient. It uses `scipy.sparse` only.

```bash
cg27 bound -j 4          # writes out/bounds.csv (250 instances: about 30 minutes)
cg27 report --run best   # the gap now uses the better of the two bounds
```

The weights also show where a tour wastes steps: `steps - weight` of a zone
is the number of steps there that the bound does not ask for (Proposition 14).
`cg27 polish` now uses this number to select 70 % of the windows of its
search. The measured gain of this selection is very small.

## 6. What is next

The baseline is a reference point. It is not a competitive solver. These are
the three best directions, in order of expected gain.

**Direction 1 — Solve the set cover first.** *Done in part: see the solver
`fekete` (5.5).*
Section 2 shows that coverage is a set cover problem on integer points.
Compute a small set of anchor points that covers the region. Then find a short
tour through that set. This is the method of Fekete et al. (ALENEX 2023, ESA
2023). It is the largest change and the largest gain.

**Direction 2 — Make the bands follow the shape.** *Done in part: see the
refiner (5.6).*
A band that crosses two thin arms and one gap pays for the full width. The
block area is 1.40 times the region area (median). If each column could put
its lanes freely, the sweep would be 21 % shorter, before the cost of the
steps between the lanes. The refiner gets part of this. Blocks of different
sizes at the border (a quadtree) could get more, but the pieces must then
connect blocks of different sizes.

**Direction 3 — Improve the division between cutters.** *Done: the solver
`fekete` cuts one tour into `k` tours. The longest tour is less than 1 %
longer than the ideal division (median).*

### How to add a solver

1. Write `src/cgshop27/solvers/<name>.py`. It must contain one function:
   `solve(instance) -> CGSHOP2027Solution`.
2. Add the name to `SOLVERS` in `src/cgshop27/solvers/__init__.py`.
3. Run it and compare it against the baseline:

```bash
cg27 solve --solver <name> --run <name> -j 8
cg27 verify --run baseline --run <name>
```

---

## 7. Dates

| Event | Date |
|---|---|
| Test instances and Python package | Released |
| Contest instances | 15 October 2026 |
| Contest closes | 31 January 2027 (AoE) |

Only valid solutions count. Equal scores break on the time of the upload.
Upload early and upload often.
