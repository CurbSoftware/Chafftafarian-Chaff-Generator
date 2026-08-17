"""VCF renderer — vCard 4.0 from world contacts (spec sections 12, 66, 74).

RFC 6350 mandates CRLF line endings; the renderer emits CRLF on every OS
so files hash identically everywhere (spec section 12's one exception,
shared with ``ics``). Contacts come from the generated world, never from
real address books (spec section 17).
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
    extension="vcf",
    supports_exact_size=False,
    supports_target_size=True,
    supports_streaming=True,
    semantic_document=None,
    size_category="contact",
)

#: One vCard is ~300-400 bytes; aim the card count at the drawn size.
_BYTES_PER_CARD = 340


def _escape(text: str) -> str:
    """Escape a vCard TEXT value (RFC 6350 section 3.4)."""
    return text.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def contact_lines(context: RenderContext) -> list[str]:
    """Build every line of the address book, CRLF-joined by the writer.

    Each world contact appears once; larger files extend the book with
    freshly synthesized people (bank names, deterministic emails) rather
    than repeating cards.
    """
    rng = context.rng
    world = context.world
    people = [world.primary_user, *world.contacts, *world.employees]

    lines: list[str] = []
    written = 0
    seen_emails: set[str] = set()
    seen_names: set[str] = set()
    for person in people:
        if written >= context.desired_size:
            break
        if person.email in seen_emails:
            continue
        seen_emails.add(person.email)
        seen_names.add(person.full_name)
        lines.extend(_card_lines(person.full_name, person.email, rng))
        written += _BYTES_PER_CARD

    extra = 0
    while written < context.desired_size and extra < 100_000:
        first = gen.pick(rng, context.bank.words("adjectives")).title()
        last = gen.pick(rng, context.bank.words("nouns")).title()
        full_name = f"{first} {last}"
        extra += 1
        if full_name in seen_names:
            continue
        seen_names.add(full_name)
        email = gen.make_email(f"{first.lower()}.{last.lower()}", "example.com")
        lines.extend(_card_lines(full_name, email, rng))
        written += _BYTES_PER_CARD
    return lines


def _card_lines(full_name: str, email: str, rng) -> list[str]:  # type: ignore[no-untyped-def]
    phone = gen.make_phone(rng)
    parts = full_name.split(" ", 1)
    family = parts[1] if len(parts) > 1 else parts[0]
    given = parts[0]
    return [
        "BEGIN:VCARD",
        "VERSION:4.0",
        f"FN:{_escape(full_name)}",
        f"N:{_escape(family)};{_escape(given)};;;",
        f"EMAIL;TYPE=WORK:{email}",
        f"TEL;TYPE=WORK:{phone}",
        "END:VCARD",
    ]


class ContactRenderer:
    id = "vcf"
    capabilities = CAPABILITIES

    def render(
        self,
        document: SemanticDocument | None,
        destination: Path,
        context: RenderContext,
    ) -> RenderResult:
        lines = contact_lines(context)
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
    if renderer_id != "vcf":
        raise ValueError(f"contact module cannot serve renderer id {renderer_id!r}")
    return ContactRenderer()
