"""The `cg27` command line: fetch, inspect, solve, verify, render, publish.

Every stage reads from and writes to the directories in `config.py`, so the
stages compose without passing paths around:

    cg27 fetch            # download and unpack the example instances
    cg27 index            # catalog.csv / catalog.json + a summary
    cg27 solve            # data/solutions/<run>/*.solution.json
    cg27 verify --run ... # feasibility and the gap to the lower bound
    cg27 render           # PNGs for instances and for a run
    cg27 gallery          # out/gallery.html tying it all together
"""

from __future__ import annotations

import argparse
import csv
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


def _map(function, items, jobs: int, label: str) -> list:
    """Run `function` over `items`, in parallel when asked, with progress."""
    results = []
    total = len(items)

    live = sys.stderr.isatty()
    step = max(1, total // 10)

    def note(index: int) -> None:
        if live:
            print(f"\r  {label}: {index}/{total}", end="", file=sys.stderr, flush=True)
        elif index % step == 0 or index == total:
            print(f"  {label}: {index}/{total}", file=sys.stderr, flush=True)

    if jobs > 1 and total > 1:
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


def _solve_worker(job: tuple[str, str, str]) -> tuple[str, int, bool, str]:
    """Solve one instance and write the solution. Returns a summary row."""
    path_text, solver_name, run = job
    from cgshop2027_pyutils.verify import check_for_errors

    path = Path(path_text)
    instance = catalog.load(path)
    solution = SOLVERS[solver_name](instance)
    errors = check_for_errors(instance, solution)
    if not errors:
        evaluate.write_solution(solution, run)
    return (
        instance.instance_uid,
        solution.max_tour_length,
        not errors,
        errors[0] if errors else "",
    )


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
    archive = config.RAW / "example_instances.zip"
    if archive.exists() and not args.force:
        print(f"already downloaded: {archive} (use --force to refetch)")
    else:
        print(f"downloading {config.EXAMPLE_INSTANCES_URL}")
        with urllib.request.urlopen(config.EXAMPLE_INSTANCES_URL) as response:
            archive.write_bytes(response.read())
        print(f"  -> {archive} ({archive.stat().st_size:,} bytes)")

    with zipfile.ZipFile(archive) as bundle:
        members = [n for n in bundle.namelist() if n.endswith(config.INSTANCE_SUFFIX)]
        bundle.extractall(config.INSTANCES, members=members)
    print(f"extracted {len(members)} instances into {config.INSTANCES}")
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

    jobs = [(str(p), args.solver, run) for p in paths]
    results = _map(_solve_worker, jobs, args.jobs, f"solving with {args.solver}")

    failed = [(uid, message) for uid, _, ok, message in results if not ok]
    print(f"\nrun {run!r}: {len(results) - len(failed)}/{len(results)} feasible")
    for uid, message in failed[:10]:
        print(f"  INFEASIBLE {uid}: {message}")
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
    path = catalog.find_instance(args.instance, args.instances)
    instance = catalog.load(path)
    solution_path = evaluate.solution_path(args.run, instance.instance_uid)
    if not solution_path.is_file():
        print(f"no solution at {solution_path}", file=sys.stderr)
        return 1
    target = animate_solution(
        instance,
        read_solution(solution_path),
        run=args.run,
        max_frames=args.frames,
        fps=args.fps,
    )
    print(target)
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


def cmd_submit(args: argparse.Namespace) -> int:
    target = Path(args.output or config.OUT / f"submission_{args.run}.zip")
    path, count = evaluate.build_submission(args.run, target)
    print(f"packed {count} solutions -> {path}")
    return 0


def _print_table(columns: list[str], rows: list[dict], limit: int = 10) -> None:
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
        print(f"... {len(rows) - limit} more (see catalog.csv)")


# -- argument parsing ------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cg27", description=__doc__.split("\n")[0])
    subparsers = parser.add_subparsers(dest="command", required=True)

    def common(sub: argparse.ArgumentParser, *, jobs: bool = True) -> None:
        sub.add_argument("--instances", type=Path, default=None,
                         help="directory to scan (default: data/instances)")
        sub.add_argument("--filter", default=None,
                         help="keep instances whose file name contains this")
        sub.add_argument("--limit", type=int, default=None,
                         help="use at most this many instances")
        if jobs:
            sub.add_argument("-j", "--jobs", type=int, default=1,
                             help="worker processes (default: 1)")

    fetch = subparsers.add_parser("fetch", help="download the example instances")
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

    animate = subparsers.add_parser("animate", help="write a GIF of one solution")
    animate.add_argument("instance")
    animate.add_argument("--run", default="boustrophedon")
    animate.add_argument("--frames", type=int, default=160)
    animate.add_argument("--fps", type=int, default=12)
    animate.add_argument("--instances", type=Path, default=None)
    animate.set_defaults(func=cmd_animate)

    page = subparsers.add_parser("gallery", help="build out/gallery.html")
    common(page)
    page.add_argument("--run", action="append", default=None)
    page.add_argument("--reindex", action="store_true", help="recompute the catalog")
    page.add_argument("--open", action="store_true", help="open in a browser")
    page.set_defaults(func=cmd_gallery)

    submit = subparsers.add_parser("submit", help="pack a run into an upload zip")
    submit.add_argument("--run", default="boustrophedon")
    submit.add_argument("-o", "--output", default=None)
    submit.set_defaults(func=cmd_submit)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
