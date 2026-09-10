"""Verifying solutions, scoring runs against each other, and packing uploads.

A "run" is one directory under `data/solutions/`, holding one
`<uid>.solution.json` per instance -- typically the output of one solver
configuration. Scoring a set of runs against each other uses the competition's
own formula, with the best objective seen locally standing in for the best
objective submitted by any team.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cgshop2027_pyutils.io import read_solution
from cgshop2027_pyutils.schemas import CGSHOP2027Instance, CGSHOP2027Solution
from cgshop2027_pyutils.verify import SolutionValidator
from cgshop2027_pyutils.zip.zip_writer import ZipWriter

from .catalog import area_lower_bound, cutter_cells, load, max_cross_section, region_cells
from .config import SOLUTION_SUFFIX, SOLUTIONS


def solution_path(run: str, instance_uid: str) -> Path:
    return SOLUTIONS / run / f"{instance_uid}{SOLUTION_SUFFIX}"


def write_solution(solution: CGSHOP2027Solution, run: str) -> Path:
    path = solution_path(run, solution.instance_uid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(solution.model_dump_json(indent=1), encoding="utf-8")
    return path


def run_names() -> list[str]:
    if not SOLUTIONS.is_dir():
        return []
    return sorted(p.name for p in SOLUTIONS.iterdir() if p.is_dir())


def run_solutions(run: str) -> list[Path]:
    return sorted((SOLUTIONS / run).glob(f"*{SOLUTION_SUFFIX}"))


@dataclass(frozen=True)
class Verdict:
    run: str
    instance_uid: str
    feasible: bool
    objective: int | None
    total_length: int
    lower_bound: int
    errors: list[str]

    @property
    def gap(self) -> float | None:
        """How far the objective is above the area lower bound, as a factor."""
        if not self.feasible or not self.objective or not self.lower_bound:
            return None
        return round(self.objective / self.lower_bound, 3)

    def as_row(self) -> dict:
        return {
            "run": self.run,
            "instance_uid": self.instance_uid,
            "feasible": self.feasible,
            "objective": self.objective,
            "total_length": self.total_length,
            "lower_bound": self.lower_bound,
            "gap": self.gap,
            "errors": self.errors,
        }


def verify(
    instance: CGSHOP2027Instance,
    solution: CGSHOP2027Solution,
    *,
    run: str = "",
    validator: SolutionValidator | None = None,
) -> Verdict:
    validator = validator or SolutionValidator(instance)
    errors = validator.check_for_errors(solution)
    region, cutter = region_cells(instance), cutter_cells(instance)
    bound = area_lower_bound(
        len(region),
        len(cutter),
        max_cross_section(cutter),
        instance.number_of_cutters,
    )
    return Verdict(
        run=run,
        instance_uid=solution.instance_uid,
        feasible=not errors,
        objective=solution.max_tour_length if not errors else None,
        total_length=solution.total_tour_length,
        lower_bound=bound,
        errors=errors,
    )


def verify_run(run: str, instance_index: dict[str, Path]) -> list[Verdict]:
    """Verify every solution of a run, reusing each instance's precomputation."""
    verdicts: list[Verdict] = []
    cache: dict[str, tuple[CGSHOP2027Instance, SolutionValidator]] = {}
    for path in run_solutions(run):
        solution = read_solution(path)
        uid = solution.instance_uid
        if uid not in instance_index:
            verdicts.append(
                Verdict(run, uid, False, None, 0, 0, [f"No instance {uid!r} found."])
            )
            continue
        if uid not in cache:
            instance = load(instance_index[uid])
            cache[uid] = (instance, SolutionValidator(instance))
        instance, validator = cache[uid]
        verdicts.append(verify(instance, solution, run=run, validator=validator))
    return verdicts


def score(verdicts: list[Verdict]) -> dict[str, float]:
    """The competition score, with the best local objective as the reference.

    `S_G(I) = B(I)^2 / B_G(I)^2`, summed over instances; an infeasible or
    missing solution scores zero.
    """
    best: dict[str, int] = {}
    for verdict in verdicts:
        if verdict.feasible and verdict.objective:
            uid = verdict.instance_uid
            best[uid] = min(best.get(uid, verdict.objective), verdict.objective)

    totals: dict[str, float] = {}
    for verdict in verdicts:
        totals.setdefault(verdict.run, 0.0)
        if verdict.feasible and verdict.objective:
            reference = best[verdict.instance_uid]
            totals[verdict.run] += (reference / verdict.objective) ** 2
    return totals


def build_submission(run: str, target: Path) -> tuple[Path, int]:
    """Pack a run into the `.zip` the competition site expects."""
    target.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with ZipWriter(target) as writer:
        for path in run_solutions(run):
            writer.add_solution(read_solution(path))
            count += 1
    return target, count
