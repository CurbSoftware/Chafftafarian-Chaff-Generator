"""Command-line interface package for Chaff Generator.

Importing the subcommand modules registers them on the shared Typer app.
"""

from __future__ import annotations

from chaff_generator.cli import generate as _generate  # noqa: F401  (registers commands)
from chaff_generator.cli import verify as _verify  # noqa: F401  (registers commands)
