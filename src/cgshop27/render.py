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

from . import config  # noqa: E402
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


FORMATS = config.ANIMATION_FORMATS


def animate_solution(
    instance: CGSHOP2027Instance,
    solution: CGSHOP2027Solution,
    *,
    run: str = "run",
    out_dir: Path | None = None,
    fmt: str = "gif",
    max_frames: int = 160,
    fps: int = 12,
    dpi: int = 70,
) -> Path:
    """Animate the cutters walking their tours, one frame per stride.

    The animation runs for as long as the longest tour, so a cutter that is
    already home just waits there. `max_frames` sets the stride: a long tour
    packed into few frames moves in big jumps, but the swept area stays exact,
    because every intermediate placement is still stamped.
    """
    if fmt not in FORMATS:
        raise ValueError(f"Unknown format {fmt!r}; expected one of {FORMATS}.")
    out_dir = out_dir or ANIMATIONS / run
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{instance.instance_uid}.{fmt}"
    animation = create_solution_animation(
        instance, solution, max_frames=max_frames, interval=int(1000 / fps)
    )
    # The library lays the figure out before the per-frame step counter exists,
    # so the counter lands on top of the figure title. Give the axes room.
    animation._fig.subplots_adjust(top=0.90)
    try:
        if fmt == "gif":
            animation.save(target, writer="pillow", fps=fps, dpi=dpi)
        else:
            from matplotlib.animation import HTMLWriter

            writer = HTMLWriter(fps=fps, embed_frames=True, default_mode="loop")
            animation.save(target, writer=writer, dpi=dpi)
    finally:
        plt.close(animation._fig)
    return target
