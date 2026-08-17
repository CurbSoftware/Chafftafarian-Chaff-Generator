"""Chaff Generator — deterministic synthetic-data corpus generator.

The public core API is :class:`chaff_generator.core.engine.ChaffEngine`,
re-exported here as ``ChaffEngine``. The package is GUI-free; PySide6 is only
imported by the :mod:`chaff_generator.gui` subpackage.
"""

from __future__ import annotations

from chaff_generator.core.engine import ChaffEngine
from chaff_generator.version import __version__

__all__ = ["ChaffEngine", "__version__"]
