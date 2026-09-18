"""Solvers. Each exposes `solve(instance, **kwargs) -> CGSHOP2027Solution`."""

from .boustrophedon import solve as boustrophedon
from .fekete import solve as fekete

SOLVERS = {"boustrophedon": boustrophedon, "fekete": fekete}

__all__ = ["SOLVERS", "boustrophedon", "fekete"]
