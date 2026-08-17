"""ICS renderer — RFC 5545 calendar from world meetings (spec sections 12, 66, 74).

CRLF line endings and 75-octet content-line folding are mandatory
(RFC 5545 section 3.1); both are byte-stable on every OS. DTSTAMP is
drawn from the configured date range, never the wall clock, so a file's
bytes depend only on its seed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from chaff_generator.content import generators as gen
from chaff_generator.renderers.base import RendererCapabilities, RenderResult
from chaff_generator.renderers.textutil import finish, open_writer

if TYPE_CHECKING:
    from pathlib import Path

    from chaff_generator.content.context import RenderContext
    from chaff_generator.renderers.base import Renderer
    from chaff_generator.renderers.documents import SemanticDocument

CAPABILITIES = RendererCapabilities(
    extension="ics",
    supports_exact_size=False,
    supports_target_size=True,
    supports_streaming=True,
    semantic_document=None,
    size_category="calendar",
)

#: One VEVENT is ~250-350 bytes; scale the event count to the drawn size.
_BYTES_PER_EVENT = 300


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> list[str]:
    """Split one content line into <=75-octet physical lines (RFC 5545 section 3.1).

    Continuation lines begin with a single space, which spends one of the
    75 octets; cuts land on UTF-8 character boundaries.
    """
    encoded = line.encode()
    if len(encoded) <= 75:
        return [line]
    parts: list[str] = []
    offset = 0
    continuation = False
    while offset < len(encoded):
        budget = 74 if continuation else 75
        cut = min(len(encoded) - offset, budget)
        while cut > 0 and offset + cut < len(encoded) and (encoded[offset + cut] & 0xC0) == 0x80:
            cut -= 1
        if cut == 0:
            cut = budget
        piece = encoded[offset : offset + cut].decode()
        parts.append((" " if continuation else "") + piece)
        offset += cut
        continuation = True
    return parts


def _utc(moment) -> str:  # type: ignore[no-untyped-def]
    return moment.strftime("%Y%m%dT%H%M%SZ")


def event_lines(context: RenderContext) -> list[str]:
    """Every physical line of the calendar, CRLF-joined by the writer."""
    from datetime import datetime, timedelta

    rng = context.rng
    world = context.world
    lines: list[str] = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Chaff Generator//Chaff 1.0//EN",
        "CALSCALE:GREGORIAN",
    ]
    written = 0
    index = 0
    meetings = world.meetings or []
    while written < context.desired_size and index < 100_000:
        if index < len(meetings):
            day = meetings[index].date
            summary_text = meetings[index].topic
        else:
            timeline = world.timeline
            if timeline is not None:
                day = timeline.draw_between(rng)
            else:
                from datetime import date as date_type

                day = date_type(2025, 6, 15)
            summary_text = context.template_engine.render_string("{{ sentence('business') }}")
        when = datetime(day.year, day.month, day.day, rng.randrange(8, 18), rng.randrange(60))
        duration = timedelta(minutes=rng.choice((30, 45, 60, 90)))
        location = _escape(f"{gen.pick(rng, context.bank.words('nouns')).title()} Room")
        stamp = when - timedelta(days=rng.randrange(1, 30))
        block = [
            "BEGIN:VEVENT",
            f"UID:{gen.make_id('evt', rng)}@chaff.example",
            f"DTSTAMP:{_utc(stamp)}",
            f"DTSTART:{_utc(when)}",
            f"DTEND:{_utc(when + duration)}",
            f"SUMMARY:{_escape(summary_text[:90])}",
            f"LOCATION:{location}",
            "END:VEVENT",
        ]
        for entry in block:
            lines.extend(_fold(entry))
        written += _BYTES_PER_EVENT
        index += 1

    lines.append("END:VCALENDAR")
    return lines


class CalendarRenderer:
    id = "ics"
    capabilities = CAPABILITIES

    def render(
        self,
        document: SemanticDocument | None,
        destination: Path,
        context: RenderContext,
    ) -> RenderResult:
        lines = event_lines(context)
        payload = ("\r\n".join(lines) + "\r\n").encode()
        handle, writer = open_writer(destination)
        with handle:
            writer.write(payload)
            finish(handle)
        return RenderResult(
            path=destination,
            size=writer.bytes_written,
            renderer_id=self.id,
            template_id=context.template_id,
            sha256=writer.digest_hex,
        )


def get_renderer(renderer_id: str) -> Renderer:
    if renderer_id != "ics":
        raise ValueError(f"calendar module cannot serve renderer id {renderer_id!r}")
    return CalendarRenderer()
