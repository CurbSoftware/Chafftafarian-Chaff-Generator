"""Render context: everything a renderer needs for one file."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chaff_generator.content.bank import ChaffBank
    from chaff_generator.content.template_engine import ChaffTemplateEngine
    from chaff_generator.content.world import GenerationWorld


@dataclass
class RenderContext:
    """Per-file context passed to every renderer.

    ``rng`` is isolated and seeded from the planned file's seed; ``engine`` is
    the Chaff template engine bound to this rng/world so Jinja helper calls
    inside one document draw from the same deterministic stream.
    """

    rng: random.Random
    world: GenerationWorld
    bank: ChaffBank
    template_engine: ChaffTemplateEngine
    desired_size: int
    run_id: str
    app_version: str
    template_id: str | None = None
    extra: dict[str, object] = field(default_factory=dict)
