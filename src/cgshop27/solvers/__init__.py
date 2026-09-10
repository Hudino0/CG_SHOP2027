"""Solvers. Each exposes `solve(instance, **kwargs) -> CGSHOP2027Solution`."""

from .boustrophedon import solve as boustrophedon

SOLVERS = {"boustrophedon": boustrophedon}

__all__ = ["SOLVERS", "boustrophedon"]
