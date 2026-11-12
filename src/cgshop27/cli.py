"""The `cg27` command line: fetch, inspect, solve, verify, render, publish.

Every stage reads from and writes to the directories in `config.py`, so the
stages compose without passing paths around:

    cg27 fetch            # download the test and the competition instances
    cg27 index            # catalog.csv / catalog.json + a summary
    cg27 solve            # data/solutions/<run>/*.solution.json
    cg27 verify --run ... # feasibility and the gap to the lower bound
    cg27 render           # PNGs for instances and for a run
    cg27 gallery          # out/gallery.html tying it all together
    cg27 overlap          # how much of the region several cutters sweep
    cg27 grid NAME        # the block grid graph of the fekete solver
    cg27 pipeline         # solve + verify + grid graph, all solvers, one report
"""

from __future__ import annotations

import argparse
import csv
import inspect
import json
import shutil
import sys
import urllib.request
import zipfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from . import catalog, config, evaluate, gallery
from .solvers import SOLVERS

# -- helpers ---------------------------------------------------------------


def _select(paths: list[Path], pattern: str | None, limit: int | None) -> list[Path]:
    if pattern:
        needle = pattern.lower()
        paths = [p for p in paths if needle in p.name.lower()]
    return paths[:limit] if limit else paths


def _instance_index(paths: list[Path]) -> dict[str, Path]:
    return {p.name.removesuffix(config.INSTANCE_SUFFIX): p for p in paths}


def _map(function, items, jobs: int, label: str, isolate: bool = False) -> list:
    """Run `function` over `items`, in parallel when asked, with progress.

    With `isolate` every item runs in a fresh process, so the memory figures
    are per item and a crash cannot take other items with it.
    """
    results = []
    total = len(items)

    live = sys.stderr.isatty()
    step = max(1, total // 10)

    def note(index: int) -> None:
        if live:
            print(f"\r  {label}: {index}/{total}", end="", file=sys.stderr, flush=True)
        elif index % step == 0 or index == total:
            print(f"  {label}: {index}/{total}", file=sys.stderr, flush=True)

    if isolate:
        import multiprocessing

        context = multiprocessing.get_context("spawn")
        with ProcessPoolExecutor(
            max_workers=max(1, jobs), mp_context=context, max_tasks_per_child=1
        ) as pool:
            futures = [pool.submit(function, item) for item in items]
            for index, future in enumerate(futures, 1):
                try:
                    results.append(future.result())
                except BaseException as error:  # noqa: BLE001 - a killed worker
                    name = Path(str(items[index - 1][0])).name
                    uid = name.removesuffix(config.INSTANCE_SUFFIX)
                    results.append((uid, 0, False, f"worker died: {type(error).__name__}"))
                note(index)
    elif jobs > 1 and total > 1:
        with ProcessPoolExecutor(max_workers=jobs) as pool:
            for index, value in enumerate(pool.map(function, items), 1):
                results.append(value)
                note(index)
    else:
        for index, item in enumerate(items, 1):
            results.append(function(item))
            note(index)
    print(file=sys.stderr)
    return results


# -- worker functions (top level, so they can be sent to subprocesses) ------


def _describe_worker(path: Path) -> catalog.InstanceStats:
    return catalog.describe(path)


def _solve_worker(job: tuple[str, str, str, dict]) -> tuple[str, int, bool, str]:
    """Solve one instance and write the solution. Returns a summary row.

    The solution is written only if the official validator accepts it. Its
    `meta` gets the wall time and the peak memory of this worker process. A
    solver that raises counts as a failure of that instance, not of the run.
    """
    path_text, solver_name, run, options = job
    import time

    from cgshop2027_pyutils.verify import check_for_errors

    options = dict(options)
    memory = options.pop("_memory_gb", None)
    keep = options.pop("_keep_best", False)
    path = Path(path_text)
    uid = path.name.removesuffix(config.INSTANCE_SUFFIX)
    try:
        import resource
    except ImportError:  # Windows
        resource = None
    if resource and memory:
        cap = int(memory * 2**30)
        resource.setrlimit(resource.RLIMIT_AS, (cap, cap))
    time_max = options.pop("_time_max", None)
    began = time.perf_counter()
    try:
        instance = catalog.load(path)
        if time_max and "time_limit" in options:
            # Large instances get more time: the limit grows with the number
            # of coarse cells, from `--time-limit` up to `--time-max`.
            from .solvers.scale import lattice_pitch

            cells = len(catalog.region_cells(instance)) / lattice_pitch(instance) ** 2
            options["time_limit"] = min(time_max, options["time_limit"] * max(1.0, cells / 30000))
        solution = SOLVERS[solver_name](instance, **options)
        errors = check_for_errors(instance, solution)
    except BaseException as error:  # noqa: BLE001 - one instance must not stop the run
        return uid, 0, False, f"{type(error).__name__}: {str(error)[:200]}"
    usage = {"solver": solver_name, "wall_seconds": round(time.perf_counter() - began, 1)}
    if resource:
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        usage["peak_memory_gb"] = round(peak / 2**20, 2)
    solution = solution.model_copy(update={"meta": {**solution.meta, **usage}})
    if not errors:
        if keep:
            evaluate.keep_best(solution, run)
        else:
            evaluate.write_solution(solution, run)
    return (
        instance.instance_uid,
        solution.max_tour_length,
        not errors,
        errors[0] if errors else "",
    )


def _overlap_worker(job: tuple[str, str, str]) -> dict:
    from cgshop2027_pyutils.io import read_solution

    from .overlap import measure

    instance_path, solution_path, run = job
    instance = catalog.load(Path(instance_path))
    return measure(instance, read_solution(Path(solution_path)), run).as_row()


def _render_instance_worker(path_text: str) -> str:
    from .render import render_instance

    return str(render_instance(catalog.load(Path(path_text))))


def _render_solution_worker(job: tuple[str, str, str]) -> str:
    from cgshop2027_pyutils.io import read_solution

    from .render import render_solution

    instance_path, solution_path, run = job
    instance = catalog.load(Path(instance_path))
    solution = read_solution(Path(solution_path))
    return str(render_solution(instance, solution, run=run))


# -- commands --------------------------------------------------------------


def cmd_fetch(args: argparse.Namespace) -> int:
    config.ensure_dirs()
    sources = {
        "test": ("example_instances.zip", config.EXAMPLE_INSTANCES_URL),
        "competition": ("challenge_instances.zip", config.CHALLENGE_INSTANCES_URL),
    }
    wanted = config.SUITES if args.suite == "all" else (args.suite,)
    for suite in wanted:
        name, url = sources[suite]
        archive = config.RAW / name
        if archive.exists() and not args.force:
            print(f"already downloaded: {archive} (use --force to refetch)")
        else:
            print(f"downloading {url}")
            with urllib.request.urlopen(url) as response:
                archive.write_bytes(response.read())
            print(f"  -> {archive} ({archive.stat().st_size:,} bytes)")
        target = config.INSTANCES / suite
        target.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive) as bundle:
            members = [m for m in bundle.namelist() if m.endswith(config.INSTANCE_SUFFIX)]
            for member in members:
                (target / Path(member).name).write_bytes(bundle.read(member))
        print(f"extracted {len(members)} {suite} instances into {target}")
    return 0


def cmd_index(args: argparse.Namespace) -> int:
    config.ensure_dirs()
    paths = _select(catalog.instance_paths(args.instances), args.filter, args.limit)
    if not paths:
        print("no instances found -- run `cg27 fetch` first", file=sys.stderr)
        return 1

    stats = _map(_describe_worker, paths, args.jobs, "describing")
    rows = [s.as_row() for s in stats]

    (config.OUT / "catalog.json").write_text(
        json.dumps(rows, indent=1), encoding="utf-8"
    )
    with (config.OUT / "catalog.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n{len(rows)} instances -> {config.OUT / 'catalog.csv'}")
    _print_table(
        ["instance_uid", "family", "number_of_cutters", "region_area", "holes",
         "cutter_width", "cutter_height", "lower_bound"],
        rows,
        limit=args.show,
    )
    areas = sorted(r["region_area"] for r in rows)
    print(
        f"\narea: min {areas[0]:,} / median {areas[len(areas) // 2]:,} / "
        f"max {areas[-1]:,}"
    )
    families = sorted({r["family"] for r in rows})
    cutters = sorted({r["number_of_cutters"] for r in rows})
    print(f"families: {', '.join(families)}")
    print(f"cutter counts: {', '.join(map(str, cutters))}")
    return 0


def cmd_solve(args: argparse.Namespace) -> int:
    config.ensure_dirs()
    paths = _select(catalog.instance_paths(args.instances), args.filter, args.limit)
    if not paths:
        print("no instances found -- run `cg27 fetch` first", file=sys.stderr)
        return 1
    run = args.run or args.solver
    if args.clean:
        shutil.rmtree(config.SOLUTIONS / run, ignore_errors=True)

    options = {}
    if args.time_limit is not None:
        if "time_limit" not in inspect.signature(SOLVERS[args.solver]).parameters:
            print(f"solver {args.solver!r} takes no --time-limit", file=sys.stderr)
            return 1
        options["time_limit"] = args.time_limit
    if args.seed is not None:
        if "seed" not in inspect.signature(SOLVERS[args.solver]).parameters:
            print(f"solver {args.solver!r} takes no --seed", file=sys.stderr)
            return 1
        options["seed"] = args.seed
    for item in args.option or []:
        key, _, value = item.partition("=")
        if key not in inspect.signature(SOLVERS[args.solver]).parameters:
            print(f"solver {args.solver!r} has no option {key!r}", file=sys.stderr)
            return 1
        options[key] = json.loads(value)
    if args.time_max:
        options["_time_max"] = args.time_max
    if args.memory_gb:
        options["_memory_gb"] = args.memory_gb
    if args.keep_best:
        options["_keep_best"] = True
    jobs = [(str(p), args.solver, run, options) for p in paths]
    results = _map(_solve_worker, jobs, args.jobs, f"solving with {args.solver}",
                   isolate=args.isolate)

    failed = [(uid, message) for uid, _, ok, message in results if not ok]
    print(f"\nrun {run!r}: {len(results) - len(failed)}/{len(results)} feasible")
    for uid, message in failed[:10]:
        print(f"  FAILED {uid}: {message}")
    print(f"solutions in {config.SOLUTIONS / run}")
    return 1 if failed else 0


def cmd_verify(args: argparse.Namespace) -> int:
    index = _instance_index(catalog.instance_paths(args.instances))
    runs = args.run or evaluate.run_names()
    if not runs:
        print("no runs under data/solutions -- run `cg27 solve` first", file=sys.stderr)
        return 1

    all_verdicts = []
    for run in runs:
        verdicts = evaluate.verify_run(run, index)
        all_verdicts.extend(verdicts)
        good = [v for v in verdicts if v.feasible]
        gaps = sorted(v.gap for v in good if v.gap)
        print(f"\nrun {run!r}: {len(good)}/{len(verdicts)} feasible")
        if gaps:
            print(
                f"  gap to area lower bound: min {gaps[0]}x / "
                f"median {gaps[len(gaps) // 2]}x / max {gaps[-1]}x"
            )
        for verdict in verdicts:
            if not verdict.feasible:
                print(f"  INFEASIBLE {verdict.instance_uid}: {verdict.errors[0]}")

    rows = [v.as_row() for v in all_verdicts]
    (config.OUT / "verdicts.json").write_text(
        json.dumps(rows, indent=1), encoding="utf-8"
    )
    if len(runs) > 1 or args.score:
        print("\ncompetition score (best local objective as reference):")
        for run, total in sorted(
            evaluate.score(all_verdicts).items(), key=lambda kv: -kv[1]
        ):
            print(f"  {total:8.3f}  {run}")
    return 0 if all(v.feasible for v in all_verdicts) else 1


def cmd_render(args: argparse.Namespace) -> int:
    config.ensure_dirs()
    paths = _select(catalog.instance_paths(args.instances), args.filter, args.limit)
    index = _instance_index(paths)

    if not args.run:
        _map(_render_instance_worker, [str(p) for p in paths], args.jobs, "rendering")
        print(f"instance renders in {config.RENDERS / 'instances'}")
        return 0

    for run in args.run:
        jobs = []
        for solution_path in evaluate.run_solutions(run):
            uid = solution_path.name.removesuffix(config.SOLUTION_SUFFIX)
            if uid in index:
                jobs.append((str(index[uid]), str(solution_path), run))
        if not jobs:
            print(f"run {run!r}: nothing to render", file=sys.stderr)
            continue
        _map(_render_solution_worker, jobs, args.jobs, f"rendering {run}")
        print(f"{run} renders in {config.RENDERS / 'solutions' / run}")
    return 0


def cmd_animate(args: argparse.Namespace) -> int:
    from cgshop2027_pyutils.io import read_solution

    from .render import animate_solution

    config.ensure_dirs()
    if args.instance:
        paths = [catalog.find_instance(args.instance, args.instances)]
    else:
        paths = _select(
            catalog.instance_paths(args.instances), args.filter, args.limit
        )
    if not paths:
        print("no instances selected", file=sys.stderr)
        return 1

    written = []
    for path in paths:
        instance = catalog.load(path)
        solution_path = evaluate.solution_path(args.run, instance.instance_uid)
        if not solution_path.is_file():
            print(f"no solution at {solution_path}", file=sys.stderr)
            continue
        target = animate_solution(
            instance,
            read_solution(solution_path),
            run=args.run,
            fmt=args.format,
            max_frames=args.frames,
            fps=args.fps,
        )
        size = target.stat().st_size
        print(f"{target}  ({size / 1e6:.1f} MB)")
        written.append(target)

    if not written:
        return 1
    if args.open:
        import webbrowser

        webbrowser.open(written[0].as_uri())
    return 0


def cmd_gallery(args: argparse.Namespace) -> int:
    config.ensure_dirs()
    paths = _select(catalog.instance_paths(args.instances), args.filter, args.limit)
    if not paths:
        print("no instances found -- run `cg27 fetch` first", file=sys.stderr)
        return 1

    cached = config.OUT / "catalog.json"
    if cached.is_file() and not args.reindex:
        wanted = set(_instance_index(paths))
        rows = [
            r
            for r in json.loads(cached.read_text(encoding="utf-8"))
            if r["instance_uid"] in wanted
        ]
        stats = [catalog.InstanceStats(**(r | {"cutter_center": tuple(r["cutter_center"])})) for r in rows]
    else:
        stats = _map(_describe_worker, paths, args.jobs, "describing")

    index = _instance_index(paths)
    runs = {}
    for run in args.run or evaluate.run_names():
        verdicts = evaluate.verify_run(run, index)
        runs[run] = {
            v.instance_uid: {
                "objective": v.objective,
                "feasible": v.feasible,
                "gap": v.gap,
            }
            for v in verdicts
        }

    target = gallery.build(stats, runs)
    print(f"gallery for {len(stats)} instances -> {target}")
    if args.open:
        import webbrowser

        webbrowser.open(target.as_uri())
    return 0


def cmd_overlap(args: argparse.Namespace) -> int:
    config.ensure_dirs()
    index = _instance_index(
        _select(catalog.instance_paths(args.instances), args.filter, args.limit)
    )
    runs = args.run or evaluate.run_names()
    rows = []
    for run in runs:
        jobs = []
        for solution_path in evaluate.run_solutions(run):
            uid = solution_path.name.removesuffix(config.SOLUTION_SUFFIX)
            if uid in index:
                jobs.append((str(index[uid]), str(solution_path), run))
        if not jobs:
            print(f"run {run!r}: no solutions", file=sys.stderr)
            continue
        found = _map(_overlap_worker, jobs, args.jobs, f"measuring {run}")
        rows.extend(found)

        several = sorted((r for r in found if r["cutters"] > 1), key=lambda r: -r["shared"])
        print(f"\nrun {run!r}: {len(several)} instances with 2 or more cutters")
        if not several:
            continue
        shares = sorted(r["shared"] for r in several)
        print(
            f"  region swept by 2+ cutters: min {shares[0]}% / "
            f"median {shares[len(shares) // 2]}% / max {shares[-1]}%"
        )
        table = [
            {
                "instance_uid": r["instance_uid"],
                "k": r["cutters"],
                "shared_%": r["shared"],
                "pairs_%": "  ".join(f"{k}:{v}" for k, v in r["pairs"].items()),
                "own_shared_%": " / ".join(str(v) for v in r["own"]),
            }
            for r in several
        ]
        _print_table(list(table[0]), table, limit=args.show, more_in="overlap.json")

    if not rows:
        print("nothing measured -- run `cg27 solve` first", file=sys.stderr)
        return 1
    target = config.OUT / "overlap.json"
    target.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"\n{len(rows)} rows -> {target}")
    return 0


def cmd_grid(args: argparse.Namespace) -> int:
    from cgshop2027_pyutils.io import read_solution

    from .gridgraph import GRIDS, draw

    config.ensure_dirs()
    path = catalog.find_instance(args.instance, args.instances)
    instance = catalog.load(path)
    solution = None
    if args.run:
        solution_path = evaluate.solution_path(args.run, instance.instance_uid)
        if not solution_path.is_file():
            print(f"no solution at {solution_path}", file=sys.stderr)
            return 1
        solution = read_solution(solution_path)
    target = GRIDS / (args.run or "instances") / f"{instance.instance_uid}.png"
    target, stats = draw(instance, solution, s=args.block, target=target)
    print(
        f"{target}\n  blocks {stats['block_size']}x{stats['block_size']}, shift {stats['shift']}: "
        f"{stats['nodes']} nodes ({stats['full_nodes']} full), {stats['edges']} edges"
    )
    if args.open:
        import webbrowser

        webbrowser.open(target.as_uri())
    return 0


def _pipeline_worker(job):
    from .pipeline import execute

    return execute(job)


def cmd_pipeline(args: argparse.Namespace) -> int:
    from . import pipeline

    config.ensure_dirs()
    paths = _select(catalog.instance_paths(args.instances), args.filter, args.limit)
    if not paths:
        print("no instances found -- run `cg27 fetch` first", file=sys.stderr)
        return 1
    solvers = args.solver or list(pipeline.DEFAULT_SOLVERS)
    options = {}
    if args.time_limit is not None:
        options["time_limit"] = args.time_limit

    jobs = []
    for solver in solvers:
        run = pipeline.run_name(args.prefix, solver)
        if args.clean:
            shutil.rmtree(config.SOLUTIONS / run, ignore_errors=True)
        opts = (
            options
            if "time_limit" in inspect.signature(SOLVERS[solver]).parameters
            else {}
        )
        jobs += [(str(p), solver, run, opts) for p in paths]
    results = _map(_pipeline_worker, jobs, args.jobs, "solve + verify + grid")

    report = pipeline.write_report(results, solvers, pipeline.REPORT_DIR / "index.html")
    summary = pipeline.write_summary(results, pipeline.REPORT_DIR / "summary.json")
    for solver in solvers:
        mine = [r for r in results if r.solver == solver]
        good = [r for r in mine if r.feasible]
        gaps = sorted(r.gap for r in good if r.gap)
        line = f"{solver}: {len(good)}/{len(mine)} feasible"
        if gaps:
            line += f", median gap {gaps[len(gaps) // 2]}x"
        print(line)
        for r in mine:
            if not r.feasible:
                print(f"  INFEASIBLE {r.instance_uid}: {r.error}")
    print(f"report  {report}\nsummary {summary}")
    if args.open:
        import webbrowser

        webbrowser.open(report.resolve().as_uri())
    return 0 if all(r.feasible for r in results) else 1


def _polish_worker(job: tuple) -> tuple[str, int, int, str]:
    """Refine one stored solution on the instance's own lattice."""
    import random
    import time

    from cgshop2027_pyutils.io import read_solution
    from cgshop2027_pyutils.schemas import CGSHOP2027Solution
    from cgshop2027_pyutils.verify import check_for_errors

    from .solvers._tour import make_tour
    from .solvers.refine import Refiner

    instance_path, solution_path, into, seconds, seed, time_max, coarse_into = job
    from .solvers import scale

    instance = catalog.load(Path(instance_path))
    solution = read_solution(Path(solution_path))
    before = solution.max_tour_length
    moving = [i for i, tour in enumerate(solution.tours) if tour.length > 0]
    paths = [list(zip(solution.tours[i].x, solution.tours[i].y)) for i in moving]
    if not paths:
        return instance.instance_uid, before, before, ""
    rng = random.Random(seed)
    began = time.perf_counter()

    # Stage 1, on the coarse lattice, while the tours still lie on it: the
    # same moves cost g * g times less there.
    g = scale.lattice_pitch(instance)
    if time_max:
        cells = len(catalog.region_cells(instance)) / g**2
        seconds = min(time_max, seconds * max(1.0, cells / 30000))
    if g > 1:
        coarse, shift = scale.coarsen(instance, g)
        on_lattice = all(
            (x - shift[0]) % g == 0 and (y - shift[1]) % g == 0 for path in paths for x, y in path
        )
        if on_lattice:
            small = [[((x - shift[0]) // g, (y - shift[1]) // g) for x, y in path] for path in paths]
            refiner = Refiner(coarse.region.mask, coarse.region.origin,
                              list(coarse.cutter.cells()), small)
            refiner.run(began + 0.75 * seconds, rng, drift=True)
            paths = [[(g * x + shift[0], g * y + shift[1]) for x, y in path]
                     for path in refiner.paths()]
            if coarse_into:
                # Keep the result that still lies on the coarse lattice: a
                # later polish can go on from it at the low cost of stage 1.
                tours = list(solution.tours)
                for i, path in zip(moving, paths):
                    tours[i] = make_tour(path)
                staged = CGSHOP2027Solution(instance_uid=solution.instance_uid, tours=tours,
                                            meta={**solution.meta, "stage": "coarse"})
                if not check_for_errors(instance, staged):
                    evaluate.keep_best(staged, coarse_into)

    # Stage 2, on the instance's own lattice.
    region, cutter = catalog.region_cells(instance), catalog.cutter_cells(instance)
    refiner = Refiner(region.mask, region.origin, list(cutter.cells()), paths)
    refiner.run(began + seconds, rng, drift=True)
    if g == 1 and coarse_into:
        coarse_into, into = None, [into, coarse_into]
    tours = list(solution.tours)
    for i, path in zip(moving, refiner.paths()):
        tours[i] = make_tour(path)
    meta = {**solution.meta, "polished_from": before}
    candidate = CGSHOP2027Solution(instance_uid=solution.instance_uid, tours=tours, meta=meta)
    errors = check_for_errors(instance, candidate)
    if errors:
        return instance.instance_uid, before, before, errors[0]
    for run in into if isinstance(into, list) else [into]:
        evaluate.keep_best(candidate, run)
    return instance.instance_uid, before, candidate.max_tour_length, ""


def cmd_polish(args: argparse.Namespace) -> int:
    """Shorten the tours of a run with the lattice refiner; keep only gains."""
    paths = _select(catalog.instance_paths(args.instances), args.filter, args.limit)
    index = _instance_index(paths)
    into = args.into or args.run
    jobs = []
    for solution_path in evaluate.run_solutions(args.run):
        uid = solution_path.name.removesuffix(config.SOLUTION_SUFFIX)
        if uid in index:
            jobs.append((str(index[uid]), str(solution_path), into, args.time_limit, args.seed,
                         args.time_max or 0.0, args.coarse_into))
    results = _map(_polish_worker, jobs, args.jobs, f"polishing {args.run}")
    gains = sorted(1 - after / before for _, before, after, _ in results if before)
    for uid, _, _, error in results:
        if error:
            print(f"  REJECTED {uid}: {error}")
    if gains:
        better = sum(1 for g in gains if g > 0)
        print(f"run {into!r}: {better}/{len(gains)} shorter, gain median "
              f"{100 * gains[len(gains) // 2]:.2f} % / max {100 * gains[-1]:.2f} %")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """One row per instance: bound, and objective, gap, time, memory per run."""
    from cgshop2027_pyutils.io import read_solution

    config.ensure_dirs()
    catalog_path = config.OUT / "catalog.json"
    if not catalog_path.is_file():
        print("no catalog -- run `cg27 index` first", file=sys.stderr)
        return 1
    stats = {r["instance_uid"]: r for r in json.loads(catalog_path.read_text(encoding="utf-8"))}
    stats = {uid: r for uid, r in stats.items() if args.suite in ("all", r["suite"])}
    runs = args.run or evaluate.run_names()
    rows = []
    for uid, stat in sorted(stats.items()):
        row = {
            "instance_uid": uid,
            "k": stat["number_of_cutters"],
            "region_area": stat["region_area"],
            "cutter_width": stat["cutter_width"],
            "lower_bound": stat["lower_bound"],
        }
        for run in runs:
            path = evaluate.solution_path(run, uid)
            if not path.is_file():
                row.update({f"{run}_objective": "", f"{run}_gap": "",
                            f"{run}_seconds": "", f"{run}_memory_gb": ""})
                continue
            solution = read_solution(path)
            objective = solution.max_tour_length
            row[f"{run}_objective"] = objective
            row[f"{run}_gap"] = round(objective / stat["lower_bound"], 4)
            row[f"{run}_seconds"] = solution.meta.get("wall_seconds", "")
            row[f"{run}_memory_gb"] = solution.meta.get("peak_memory_gb", "")
        rows.append(row)
    target = Path(args.output or config.OUT / "results.csv")
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    best = {}
    for row in rows:
        values = [row[f"{run}_objective"] for run in runs if row[f"{run}_objective"] != ""]
        if values:
            best[row["instance_uid"]] = min(values)
    print(f"{len(rows)} instances, {len(runs)} runs -> {target}")
    print(f"{'run':<14}{'solved':>7}{'gap min':>9}{'median':>8}{'max':>8}{'score':>9}"
          f"{'max s':>8}{'max GB':>8}")
    for run in runs:
        have = [r for r in rows if r[f"{run}_objective"] != ""]
        if not have:
            continue
        gaps = sorted(r[f"{run}_gap"] for r in have)
        score = sum((best[r["instance_uid"]] / r[f"{run}_objective"]) ** 2 for r in have)
        seconds = [r[f"{run}_seconds"] for r in have if r[f"{run}_seconds"] != ""]
        memory = [r[f"{run}_memory_gb"] for r in have if r[f"{run}_memory_gb"] != ""]
        print(f"{run:<14}{len(have):>7}{gaps[0]:>9.3f}{gaps[len(gaps) // 2]:>8.3f}"
              f"{gaps[-1]:>8.3f}{score:>9.2f}"
              f"{max(seconds) if seconds else float('nan'):>8.0f}"
              f"{max(memory) if memory else float('nan'):>8.2f}")
    return 0


def cmd_campaign(args: argparse.Namespace) -> int:
    """The whole chain in one command: solve with every solver, keep the best, pack.

    Seeds are fixed, but the solvers stop on a time limit, so a faster machine
    gets further in the same seconds. The `best` run only improves, so running
    the campaign again (or with another seed) never loses a solution.
    """
    suite = str(config.INSTANCES / args.suite)
    shared = ["--instances", suite, "-j", str(args.jobs)]
    if args.filter:
        shared += ["--filter", args.filter]
    steps = [["index", "-j", str(args.jobs), "--show", "0"]]
    steps.append(["solve", *shared, "--solver", "boustrophedon", "--run", "baseline"])
    for solver in ("fekete", "lanes"):
        steps.append([
            "solve", *shared, "--solver", solver, "--run", f"{solver}_s{args.seed}",
            "--time-limit", str(args.time_limit), "--seed", str(args.seed),
            "--isolate", "--memory-gb", str(args.memory_gb),
        ])
    steps.append(["best", "--instances", suite])
    steps.append(["polish", *shared, "--run", "best", "--time-limit", str(args.polish_limit),
                  "--seed", str(args.seed)])
    steps.append(["submit", "--run", "best", "--check", args.suite])
    steps.append(["report", "--suite", args.suite])
    for step in steps:
        print(f"\n== cg27 {' '.join(step)}", flush=True)
        code = main(step)
        # A solver may fail single instances; the best run still holds the rest.
        if code and step[0] not in ("solve",):
            return code
    return 0


def cmd_grind(args: argparse.Namespace) -> int:
    """Rounds of new solutions from other seeds and grid offsets; `best` keeps the gains.

    The solvers reach the level of their model within seconds, and another
    seed or grid offset gives another tour of about the same length (spread
    about 1 % to 3 %). So many short runs beat one long run. Each round
    solves with `fekete` (grid offset and seed = round number) and `lanes`
    (seed = round number), polishes the round on the fine lattice, and merges
    it into `best`.
    """
    suite = str(config.INSTANCES / args.suite)
    shared = ["--instances", suite, "-j", str(args.jobs)]
    if args.filter:
        shared += ["--filter", args.filter]
    for number in range(args.first, args.first + args.rounds):
        plan = {"anchors": [], "fekete": ["-O", f"shift={number}"], "lanes": []}
        for solver in args.solver or list(plan):
            extra = plan[solver]
            run = f"round_{solver}"
            steps = [
                ["solve", *shared, "--solver", solver, "--run", run, "--clean",
                 "--time-limit", str(args.time_limit), "--time-max", str(args.time_max),
                 "--seed", str(number), "--isolate", "--memory-gb", str(args.memory_gb), *extra],
                ["polish", *shared, "--run", run, "--into", "best",
                 "--coarse-into", "best_coarse", "--time-limit", str(args.polish_limit),
                 "--time-max", str(args.polish_max), "--seed", str(number)],
            ]
            for step in steps:
                print(f"\n== round {number}: cg27 {' '.join(step)}", flush=True)
                main(step)
        main(["submit", "--run", "best", "--check", args.suite])
        main(["report", "--suite", args.suite, "--run", "best"])
    return 0


def cmd_best(args: argparse.Namespace) -> int:
    """Merge runs into one run that keeps the best verified solution of each instance."""
    from cgshop2027_pyutils.io import read_solution
    from cgshop2027_pyutils.verify import SolutionValidator

    index = _instance_index(catalog.instance_paths(args.instances))
    candidates: dict[str, list[tuple[int, str, Path]]] = {}
    for run in args.run or [r for r in evaluate.run_names() if r != args.into]:
        for path in evaluate.run_solutions(run):
            uid = path.name.removesuffix(config.SOLUTION_SUFFIX)
            if uid in index:
                candidates.setdefault(uid, []).append((0, run, path))
    improved, wins = 0, {}
    for uid, entries in sorted(candidates.items()):
        current = evaluate.solution_path(args.into, uid)
        held = read_solution(current).max_tour_length if current.is_file() else None
        loaded = [(read_solution(path), run) for _, run, path in entries]
        loaded.sort(key=lambda pair: pair[0].max_tour_length)
        validator = None
        for solution, run in loaded:
            if held is not None and solution.max_tour_length >= held:
                break
            # Never trust a file: verify before it may replace the held one.
            validator = validator or SolutionValidator(catalog.load(index[uid]))
            if validator.check_for_errors(solution):
                print(f"  INFEASIBLE {uid} in run {run!r}: skipped", file=sys.stderr)
                continue
            evaluate.keep_best(solution, args.into)
            improved += 1
            wins[run] = wins.get(run, 0) + 1
            break
    have = len(evaluate.run_solutions(args.into))
    print(f"run {args.into!r}: {have} solutions, {improved} improved this time")
    for run, count in sorted(wins.items(), key=lambda kv: -kv[1]):
        print(f"  {count:4d} from {run}")
    return 0


def cmd_submit(args: argparse.Namespace) -> int:
    target = Path(args.output or config.OUT / f"submission_{args.run}.zip")
    path, count = evaluate.build_submission(args.run, target)
    print(f"packed {count} solutions -> {path}")
    if args.check:
        index = _instance_index(catalog.instance_paths(config.INSTANCES / args.check))
        problems = evaluate.check_submission(path, index)
        for problem in problems[:20]:
            print(f"  PROBLEM {problem}")
        print(f"official check against {len(index)} {args.check} instances: "
              f"{'OK' if not problems else f'{len(problems)} problems'}")
        return 1 if problems else 0
    return 0


def _print_table(
    columns: list[str], rows: list[dict], limit: int = 10, more_in: str = "catalog.csv"
) -> None:
    if not rows or limit == 0:
        return
    shown = rows[:limit]
    widths = [
        max(len(c), *(len(f"{r[c]:,}" if isinstance(r[c], int) else str(r[c])) for r in shown))
        for c in columns
    ]
    print("  ".join(c.ljust(w) for c, w in zip(columns, widths)))
    print("  ".join("-" * w for w in widths))
    for row in shown:
        cells = [f"{row[c]:,}" if isinstance(row[c], int) else str(row[c]) for c in columns]
        print("  ".join(cell.ljust(w) for cell, w in zip(cells, widths)))
    if len(rows) > limit:
        print(f"... {len(rows) - limit} more (see {more_in})")


# -- argument parsing ------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cg27", description=__doc__.split("\n")[0])
    subparsers = parser.add_subparsers(dest="command", required=True)

    def common(sub: argparse.ArgumentParser, *, jobs: bool = True) -> None:
        sub.add_argument("--instances", type=Path, default=None,
                         help="directory to scan (default: instances/)")
        sub.add_argument("--filter", default=None,
                         help="keep instances whose file name contains this")
        sub.add_argument("--limit", type=int, default=None,
                         help="use at most this many instances")
        if jobs:
            sub.add_argument("-j", "--jobs", type=int, default=1,
                             help="worker processes (default: 1)")

    fetch = subparsers.add_parser(
        "fetch", help="download the test and competition instances"
    )
    fetch.add_argument("--suite", choices=("all", *config.SUITES), default="all",
                       help="which instances to get (default: all)")
    fetch.add_argument("--force", action="store_true", help="redownload the archive")
    fetch.set_defaults(func=cmd_fetch)

    index = subparsers.add_parser("index", help="build the instance catalog")
    common(index)
    index.add_argument("--show", type=int, default=10, help="rows to print")
    index.set_defaults(func=cmd_index)

    solve = subparsers.add_parser("solve", help="run a solver over the instances")
    common(solve)
    solve.add_argument("--solver", choices=sorted(SOLVERS), default="boustrophedon")
    solve.add_argument("--run", default=None, help="name of the output run")
    solve.add_argument("--clean", action="store_true", help="empty the run first")
    solve.add_argument("--time-limit", type=float, default=None,
                       help="seconds per instance, for solvers that take it")
    solve.add_argument("--time-max", type=float, default=None,
                       help="let --time-limit grow with the instance size, up to this")
    solve.add_argument("-O", "--option", action="append", default=None, metavar="KEY=VALUE",
                       help="another option of the solver, e.g. -O shift=3 (repeat it)")
    solve.add_argument("--seed", type=int, default=None,
                       help="random seed, for solvers that take it (default: 0)")
    solve.add_argument("--isolate", action="store_true",
                       help="one fresh process per instance: exact memory figures, "
                            "and a crash stays local")
    solve.add_argument("--memory-gb", type=float, default=None,
                       help="memory limit per worker (not on Windows)")
    solve.add_argument("--keep-best", action="store_true",
                       help="never replace a stored solution by a longer one")
    solve.set_defaults(func=cmd_solve)

    verify = subparsers.add_parser("verify", help="check runs and compare them")
    common(verify, jobs=False)
    verify.add_argument("--run", action="append", default=None)
    verify.add_argument("--score", action="store_true", help="always print scores")
    verify.set_defaults(func=cmd_verify)

    render = subparsers.add_parser("render", help="render instances or solutions")
    common(render)
    render.add_argument("--run", action="append", default=None,
                        help="render this run's solutions instead of the instances")
    render.set_defaults(func=cmd_render)

    animate = subparsers.add_parser("animate", help="animate a run's tours over time")
    animate.add_argument("instance", nargs="?", default=None,
                         help="one instance; omit it and use --filter for a batch")
    animate.add_argument("--run", default="baseline", help="run to animate")
    animate.add_argument("--format", choices=config.ANIMATION_FORMATS, default="html",
                         help="html has play, pause and a time slider; gif travels well")
    animate.add_argument("--frames", type=int, default=160,
                         help="frame budget; more frames means a finer stride")
    animate.add_argument("--fps", type=int, default=12)
    animate.add_argument("--open", action="store_true", help="open the first result")
    animate.add_argument("--instances", type=Path, default=None)
    animate.add_argument("--filter", default=None)
    animate.add_argument("--limit", type=int, default=None)
    animate.set_defaults(func=cmd_animate)

    page = subparsers.add_parser("gallery", help="build out/gallery.html")
    common(page)
    page.add_argument("--run", action="append", default=None)
    page.add_argument("--reindex", action="store_true", help="recompute the catalog")
    page.add_argument("--open", action="store_true", help="open in a browser")
    page.set_defaults(func=cmd_gallery)

    over = subparsers.add_parser("overlap", help="measure how much the tours overlap")
    common(over)
    over.add_argument("--run", action="append", default=None,
                      help="run to measure (repeat it; default: all runs)")
    over.add_argument("--show", type=int, default=10, help="rows to print per run")
    over.set_defaults(func=cmd_overlap)

    grid = subparsers.add_parser("grid", help="draw the block grid graph of the fekete solver")
    grid.add_argument("instance", help="instance uid, file name or path")
    grid.add_argument("--run", default=None,
                      help="draw this run's tours on top, and use its block size")
    grid.add_argument("--block", type=int, default=None,
                      help="block size s (default: the run's, else the cutter width)")
    grid.add_argument("--instances", type=Path, default=None)
    grid.add_argument("--open", action="store_true", help="open the image")
    grid.set_defaults(func=cmd_grid)

    pipe = subparsers.add_parser(
        "pipeline", help="solve, verify and draw the grid graph, for several solvers"
    )
    common(pipe)
    pipe.add_argument("--solver", action="append", choices=sorted(SOLVERS), default=None,
                      help="solver to run; repeat for more (default: all)")
    pipe.add_argument("--prefix", default="pipe", help="runs are named <prefix>_<solver>")
    pipe.add_argument("--clean", action="store_true", help="empty the runs first")
    pipe.add_argument("--time-limit", type=float, default=None,
                      help="seconds per instance, for the solvers that take it")
    pipe.add_argument("--open", action="store_true", help="open the report")
    pipe.set_defaults(func=cmd_pipeline)

    polish = subparsers.add_parser(
        "polish", help="shorten a run's tours with the lattice refiner; keep only gains"
    )
    common(polish)
    polish.add_argument("--run", default="best", help="run to read")
    polish.add_argument("--into", default=None, help="run to write (default: the same run)")
    polish.add_argument("--time-limit", type=float, default=20.0,
                        help="seconds per instance (default: 20)")
    polish.add_argument("--time-max", type=float, default=None,
                        help="let --time-limit grow with the instance size, up to this")
    polish.add_argument("--coarse-into", default=None,
                        help="also keep the result of the coarse stage in this run")
    polish.add_argument("--seed", type=int, default=0)
    polish.set_defaults(func=cmd_polish)

    campaign = subparsers.add_parser(
        "campaign", help="solve with every solver, keep the best, polish, pack and report"
    )
    campaign.add_argument("--suite", choices=config.SUITES, default="competition")
    campaign.add_argument("--filter", default=None)
    campaign.add_argument("-j", "--jobs", type=int, default=4)
    campaign.add_argument("--time-limit", type=float, default=30.0,
                          help="seconds per instance and solver (default: 30)")
    campaign.add_argument("--polish-limit", type=float, default=20.0,
                          help="seconds per instance for the final refinement")
    campaign.add_argument("--memory-gb", type=float, default=10.0,
                          help="memory limit per worker (default: 10)")
    campaign.add_argument("--seed", type=int, default=0)
    campaign.set_defaults(func=cmd_campaign)

    grind = subparsers.add_parser(
        "grind", help="rounds of other seeds and grid offsets; the run best keeps the gains"
    )
    grind.add_argument("--suite", choices=config.SUITES, default="competition")
    grind.add_argument("--filter", default=None)
    grind.add_argument("-j", "--jobs", type=int, default=4)
    grind.add_argument("--rounds", type=int, default=1)
    grind.add_argument("--solver", action="append", choices=("anchors", "fekete", "lanes"),
                       default=None, help="solver of each round (repeat it; default: all)")
    grind.add_argument("--first", type=int, default=1, help="number of the first round")
    grind.add_argument("--time-limit", type=float, default=8.0)
    grind.add_argument("--time-max", type=float, default=60.0)
    grind.add_argument("--polish-limit", type=float, default=20.0)
    grind.add_argument("--polish-max", type=float, default=120.0)
    grind.add_argument("--memory-gb", type=float, default=10.0)
    grind.set_defaults(func=cmd_grind)

    report = subparsers.add_parser(
        "report", help="write out/results.csv: bound, objective, gap, time and memory"
    )
    report.add_argument("--run", action="append", default=None,
                        help="run to include (repeat it; default: all runs)")
    report.add_argument("--suite", choices=("all", *config.SUITES), default="competition")
    report.add_argument("-o", "--output", default=None)
    report.set_defaults(func=cmd_report)

    best = subparsers.add_parser(
        "best", help="merge runs, keeping the best verified solution of each instance"
    )
    best.add_argument("--run", action="append", default=None,
                      help="run to take from (repeat it; default: all runs)")
    best.add_argument("--into", default="best", help="the run that only improves")
    best.add_argument("--instances", type=Path, default=None)
    best.set_defaults(func=cmd_best)

    submit = subparsers.add_parser("submit", help="pack a run into an upload zip")
    submit.add_argument("--run", default="boustrophedon")
    submit.add_argument("-o", "--output", default=None)
    submit.add_argument("--check", choices=config.SUITES, default=None,
                        help="read the zip back and verify it against this suite")
    submit.set_defaults(func=cmd_submit)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
