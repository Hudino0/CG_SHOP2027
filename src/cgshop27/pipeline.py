"""One command from instance to grid graph picture, for several algorithms.

For each instance and each solver the pipeline does four things:

1. solve the instance and keep the solution only if the verifier accepts it,
2. verify it and compute the gap to the lower bound,
3. draw the block grid graph with the tours of that solver on top,
4. write one HTML report that puts all solvers side by side.

The runs are named `<prefix>_<solver>`, so they sit next to the runs made by
`cg27 solve` and every other command (`verify`, `animate`, `submit`) reads
them.
"""

from __future__ import annotations

import html
import json
import time
from dataclasses import dataclass
from pathlib import Path

from cgshop2027_pyutils.io import read_solution
from cgshop2027_pyutils.verify import SolutionValidator

from . import catalog, evaluate
from .config import OUT
from .gridgraph import GRIDS, draw
from .solvers import SOLVERS

REPORT_DIR = OUT / "pipeline"

#: The solvers to run when none is named, simplest first.
DEFAULT_SOLVERS = ("boustrophedon", "fekete")


@dataclass
class Result:
    instance_uid: str
    solver: str
    run: str
    feasible: bool
    objective: int | None
    lower_bound: int
    gap: float | None
    seconds: float
    grid_image: str | None
    nodes: int | None
    edges: int | None
    block_size: int | None
    error: str = ""

    def as_row(self) -> dict:
        return self.__dict__.copy()


def run_name(prefix: str, solver: str) -> str:
    return f"{prefix}_{solver}"


def execute(job: tuple[str, str, str, dict]) -> Result:
    """Solve, verify and draw one (instance, solver) pair. Top level, so a
    process pool can run it."""
    path_text, solver, run, options = job
    instance = catalog.load(Path(path_text))
    uid = instance.instance_uid

    started = time.perf_counter()
    solution = SOLVERS[solver](instance, **options)
    seconds = time.perf_counter() - started

    verdict = evaluate.verify(
        instance, solution, run=run, validator=SolutionValidator(instance)
    )
    if not verdict.feasible:
        return Result(uid, solver, run, False, None, verdict.lower_bound, None,
                      round(seconds, 2), None, None, None, None, verdict.errors[0])

    evaluate.write_solution(solution, run)
    # Read it back: the picture then shows what is on disk, not what is in memory.
    saved = read_solution(evaluate.solution_path(run, uid))
    image, stats = draw(instance, saved, target=GRIDS / run / f"{uid}.png")
    return Result(uid, solver, run, True, verdict.objective, verdict.lower_bound,
                  verdict.gap, round(seconds, 2), str(image.relative_to(OUT)),
                  stats["nodes"], stats["edges"], stats["block_size"])


def write_report(results: list[Result], solvers: list[str], target: Path) -> Path:
    """An HTML table: one row per instance, one column per solver."""
    target.parent.mkdir(parents=True, exist_ok=True)
    by_instance: dict[str, dict[str, Result]] = {}
    for result in results:
        by_instance.setdefault(result.instance_uid, {})[result.solver] = result

    head = "".join(f"<th>{html.escape(s)}</th>" for s in solvers)
    rows = []
    for uid in sorted(by_instance):
        cells = []
        for solver in solvers:
            r = by_instance[uid].get(solver)
            if r is None:
                cells.append("<td>-</td>")
            elif not r.feasible:
                cells.append(f"<td class=bad>INFEASIBLE<br><small>{html.escape(r.error)}</small></td>")
            else:
                image = Path("..") / r.grid_image
                cells.append(
                    f"<td><a href='{image.as_posix()}'><img src='{image.as_posix()}' loading=lazy></a>"
                    f"<br><b>{r.objective}</b> · gap {r.gap}x · {r.seconds}s"
                    f"<br><small>bloques {r.block_size}x{r.block_size}: {r.nodes} nodos, {r.edges} aristas</small></td>"
                )
        rows.append(f"<tr><th>{html.escape(uid)}</th>{''.join(cells)}</tr>")

    target.write_text(
        "<!doctype html><meta charset=utf-8><title>Pipeline CG:SHOP 2027</title>"
        "<style>body{font:14px sans-serif;margin:1rem}table{border-collapse:collapse}"
        "td,th{border:1px solid #ccc;padding:6px;vertical-align:top;text-align:left}"
        "img{width:340px}.bad{color:#b00}</style>"
        f"<h1>Pipeline CG:SHOP 2027</h1><table><tr><th>instancia</th>{head}</tr>"
        f"{''.join(rows)}</table>",
        encoding="utf-8",
    )
    return target


def write_summary(results: list[Result], target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps([r.as_row() for r in results], indent=1), encoding="utf-8")
    return target
