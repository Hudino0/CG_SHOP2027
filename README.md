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

This writes 75 example instances into `data/instances/`. The repository does
not carry them, so this step is necessary after each new clone.

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

The full set uses 2.4 MB in `data/` and 17 MB in `out/`.

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
| `src/cgshop27/solvers/_tour.py` | Converts waypoints into tours that the schema accepts. |
| `src/cgshop27/cli.py` | The `cg27` command and its 8 sub-commands. |

The pipeline writes into these directories. Git ignores all of them.

| Directory | Content |
|---|---|
| `data/instances/` | The instance files. Command `cg27 fetch` gets them. |
| `data/solutions/<run>/` | The solution files. One directory for each run. |
| `out/catalog.csv` | One line for each instance, with all size numbers. |
| `out/verdicts.json` | Result, objective and gap for each solution. |
| `out/gallery.html` | The HTML page to browse the instances. |
| `out/renders/` | The PNG images. |
| `out/animations/` | The animations. |

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
cg27 submit --run baseline          # write out/submission_baseline.zip
```

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

## 6. What is next

The baseline is a reference point. It is not a competitive solver. These are
the three best directions, in order of expected gain.

**Direction 1 — Solve the set cover first.**
Section 2 shows that coverage is a set cover problem on integer points.
Compute a small set of anchor points that covers the region. Then find a short
tour through that set. This is the method of Fekete et al. (ALENEX 2023, ESA
2023). It is the largest change and the largest gain.

**Direction 2 — Make the bands follow the shape.**
A band that crosses two thin arms and one gap pays for the full width. Cut each
band into separate runs. Then decide the order of the runs.

**Direction 3 — Improve the division between cutters.**
Today each cutter gets a horizontal slab. If the region has two separate parts,
one cutter for each part is much better. Remove the condition that the groups
must be adjacent.

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
