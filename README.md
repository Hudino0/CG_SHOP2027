# CG:SHOP 2027 — pipeline

Tools to download, draw, solve and check the instances of the Ninth
Computational Geometry Challenge. The problem is **Multi-Robot Lawn Mowing for
Polyominoes**.

- Competition page: <https://cgshop.ibr.cs.tu-bs.de/competition/cg-shop-2027/>
- Official Python package: <https://github.com/CG-SHOP/pyutils27>

This project uses the official package. Therefore the reader, the verifier and
the plots agree with the verifier of the upload site.

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
| `src/cgshop27/render.py` | Writes PNG images and GIF animations. |
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
| `out/renders/`, `out/animations/` | The images and the animations. |

A **run** is one directory of solutions. It is normally the output of one
solver. Use one run for each experiment.

---

## 4. How to run it

Install the package one time:

```bash
python -m venv .venv && .venv/Scripts/python -m pip install -e .
```

Then run the pipeline:

```bash
cg27 fetch                          # download the example instances
cg27 index -j 8                     # write out/catalog.csv
cg27 solve -j 8 --run baseline      # write data/solutions/baseline/
cg27 verify --score                 # check the solutions and score them
cg27 render -j 8                    # draw the instances
cg27 render -j 8 --run baseline     # draw the solutions of one run
cg27 gallery --open                 # write and open out/gallery.html
cg27 animate iso_11k_6k_3p --run baseline
cg27 submit --run baseline          # write out/submission_baseline.zip
```

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
