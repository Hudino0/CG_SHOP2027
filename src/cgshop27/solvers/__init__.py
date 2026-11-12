"""Solvers. Each exposes `solve(instance, **kwargs) -> CGSHOP2027Solution`."""

from .anchors import solve as _anchors
from .boustrophedon import solve as boustrophedon
from .fekete import solve as _fekete
from .lanes import solve as _lanes
from .scale import scaled

# The compiled block search holds a block in one 64-bit mask, so a block is at
# most 7 cells wide. `scaled` solves on the instance's own coarse lattice
# (exact) and coarsens further only when the cutter is still wider than that.
fekete = scaled(_fekete, max_width=7)

# Lanes have no blocks: the instance's own lattice is enough, at any width.
lanes = scaled(_lanes)

# Anchors: a low-spill cover by stamps first, then a tour, then the refiner.
anchors = scaled(_anchors)

SOLVERS = {"boustrophedon": boustrophedon, "fekete": fekete, "lanes": lanes, "anchors": anchors}

__all__ = ["SOLVERS", "anchors", "boustrophedon", "fekete", "lanes", "scaled"]
