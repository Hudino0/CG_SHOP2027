"""Project layout: every path the pipeline reads or writes lives here."""

from __future__ import annotations

import os
from pathlib import Path

# The project root is the directory holding `pyproject.toml`, so the CLI works
# from any working directory. `CG27_ROOT` overrides it.
ROOT = Path(os.environ.get("CG27_ROOT", Path(__file__).resolve().parents[2]))

DATA = ROOT / "data"
RAW = DATA / "raw"
INSTANCES = DATA / "instances"
SOLUTIONS = DATA / "solutions"
OUT = ROOT / "out"
RENDERS = OUT / "renders"
ANIMATIONS = OUT / "animations"

#: Where the organizers publish the example instances.
EXAMPLE_INSTANCES_URL = (
    "https://cgshop.ibr.cs.tu-bs.de/content_management/media/"
    "cgshop_2027_example_instances"
)

#: What `cg27 animate` can write. GIF travels well; HTML is the one to study
#: a route with, because it has play, pause and a time slider.
ANIMATION_FORMATS = ("html", "gif")

INSTANCE_SUFFIX = ".instance.json"
SOLUTION_SUFFIX = ".solution.json"


def ensure_dirs() -> None:
    for path in (RAW, INSTANCES, SOLUTIONS, OUT, RENDERS, ANIMATIONS):
        path.mkdir(parents=True, exist_ok=True)
