"""COMPAT SHIM — studio physics compositions moved to ``pieces/physics.py``."""

from __future__ import annotations

from .pieces.physics import _analytic_chirp, _read_strain, gw150914  # noqa: F401
