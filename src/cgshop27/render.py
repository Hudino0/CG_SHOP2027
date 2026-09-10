"""Rendering instances and solutions to image files.

The drawing itself is the official `cgshop2027_pyutils.visualize`; this module
only takes care of the batch side: a headless backend, consistent file names,
and closing figures so a run over hundreds of instances does not grow without
bound.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from cgshop2027_pyutils.schemas import (  # noqa: E402
    CGSHOP2027Instance,
    CGSHOP2027Solution,
)
from cgshop2027_pyutils.visualize import (  # noqa: E402
    create_instance_plot,
    create_solution_animation,
    create_solution_plot,
)

from .config import ANIMATIONS, RENDERS  # noqa: E402


def render_instance(
    instance: CGSHOP2027Instance,
    *,
    out_dir: Path | None = None,
    dpi: int = 90,
    bare: bool = False,
) -> Path:
    out_dir = out_dir or RENDERS / "instances"
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{instance.instance_uid}.png"
    figure = create_instance_plot(instance, bare=bare)
    try:
        figure.savefig(target, dpi=dpi, bbox_inches="tight")
    finally:
        plt.close(figure)
    return target


def render_solution(
    instance: CGSHOP2027Instance,
    solution: CGSHOP2027Solution,
    *,
    run: str = "run",
    out_dir: Path | None = None,
    dpi: int = 90,
    bare: bool = False,
) -> Path:
    out_dir = out_dir or RENDERS / "solutions" / run
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{instance.instance_uid}.png"
    figure = create_solution_plot(instance, solution, bare=bare)
    try:
        figure.savefig(target, dpi=dpi, bbox_inches="tight")
    finally:
        plt.close(figure)
    return target


def animate_solution(
    instance: CGSHOP2027Instance,
    solution: CGSHOP2027Solution,
    *,
    run: str = "run",
    out_dir: Path | None = None,
    max_frames: int = 160,
    fps: int = 12,
    dpi: int = 70,
) -> Path:
    """Write a GIF of the cutters walking their tours."""
    out_dir = out_dir or ANIMATIONS / run
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{instance.instance_uid}.gif"
    animation = create_solution_animation(
        instance, solution, max_frames=max_frames, interval=int(1000 / fps)
    )
    try:
        animation.save(target, writer="pillow", fps=fps, dpi=dpi)
    finally:
        plt.close(animation._fig)
    return target
