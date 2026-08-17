"""Service event-log renderer (exact-size capable, spec sections 20, 67).

Self-generating: no template. Produces realistic syslog-style lines —
monotonically advancing timestamps, weighted levels, service names derived
from the pack's technology bank, messages drawn from the technical sentence
bank. Streams until exactly ``desired_size`` bytes.
"""

from __future__ import annotations

import random
from collections.abc import Iterator
from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING

from chaff_generator.content import generators as gen
from chaff_generator.renderers.base import RendererCapabilities, RenderResult
from chaff_generator.renderers.textutil import finish, open_writer, write_chunks_exact

if TYPE_CHECKING:
    from pathlib import Path

    from chaff_generator.content.context import RenderContext
    from chaff_generator.renderers.base import Renderer
    from chaff_generator.renderers.documents import SemanticDocument

CAPABILITIES = RendererCapabilities(
    extension="log",
    supports_exact_size=True,
    supports_target_size=True,
    supports_streaming=True,
    semantic_document=None,
    size_category="log",
)

_LEVELS = ("INFO", "INFO", "INFO", "INFO", "WARN", "DEBUG", "ERROR")
_ROLES = ("service", "gateway", "worker", "scheduler", "api", "queue", "auth")


def _start_timestamp(context: RenderContext, rng: random.Random) -> datetime:
    timeline = context.world.timeline
    day: date = timeline.draw_between(rng) if timeline is not None else date(2025, 6, 15)
    return datetime.combine(day, time(rng.randrange(0, 24), rng.randrange(0, 60), 0))


def _services(context: RenderContext, rng: random.Random) -> list[str]:
    technologies = context.bank.words("technologies")
    if not technologies:
        return ["core-service"]
    return [
        f"{gen.pick(rng, _ROLES)}-{gen.pick(rng, technologies).lower().replace(' ', '-')}"
        for _ in range(6)
    ]


def log_chunks(context: RenderContext) -> Iterator[str]:
    """Yield log lines forever; timestamps advance a few seconds per line."""
    rng = context.rng
    moment = _start_timestamp(context, rng)
    services = _services(context, rng)
    while True:
        moment += timedelta(seconds=rng.randrange(1, 240))
        level = gen.pick(rng, _LEVELS)
        service = gen.pick(rng, services)
        message = context.template_engine.render_string("{{ sentence('technical') }}")
        trace = f"{rng.getrandbits(48):012x}"
        yield (
            f"{moment.isoformat(timespec='seconds')}Z {level:<5} "
            f"[{service}] {message} (trace={trace})\n"
        )


class LogRenderer:
    id = "log"
    capabilities = CAPABILITIES

    def render(
        self,
        document: SemanticDocument | None,
        destination: Path,
        context: RenderContext,
    ) -> RenderResult:
        handle, writer = open_writer(destination)
        with handle:
            write_chunks_exact(writer, log_chunks(context), context.desired_size)
            finish(handle)
        return RenderResult(
            path=destination,
            size=writer.bytes_written,
            renderer_id=self.id,
            template_id=context.template_id,
            sha256=writer.digest_hex,
        )


def get_renderer(renderer_id: str) -> Renderer:
    if renderer_id != "log":
        raise ValueError(f"log module cannot serve renderer id {renderer_id!r}")
    return LogRenderer()
