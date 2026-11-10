"""Solvers. Each exposes `solve(instance, **kwargs) -> CGSHOP2027Solution`."""

from .boustrophedon import solve as boustrophedon
from .fekete import solve as _fekete
from .scale import scaled

# The compiled block search holds a block in one 64-bit mask, so a block is at
# most 7 cells wide. `scaled` solves on the instance's own coarse lattice
# (exact) and coarsens further only when the cutter is still wider than that.
fekete = scaled(_fekete, max_width=7)

SOLVERS = {"boustrophedon": boustrophedon, "fekete": fekete}

__all__ = ["SOLVERS", "boustrophedon", "fekete", "scaled"]
