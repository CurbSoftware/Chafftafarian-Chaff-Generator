"""Markdown renderer (approximate size, spec sections 20, 67).

Consumes a :class:`ProseDocument`; after the document body is emitted the
renderer appends filler sections (heading + paragraphs from the sentence
banks) until the desired size is reached.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from typing import TYPE_CHECKING

from chaff_generator.content.builders import filler_paragraph
from chaff_generator.renderers.base import RendererCapabilities, RenderResult
from chaff_generator.renderers.documents import (
    BulletList,
    Heading,
    NumberedList,
    PageBreak,
    Paragraph,
    ProseDocument,
    Quote,
    Table,
)
from chaff_generator.renderers.textutil import finish, open_writer, write_chunks_until

if TYPE_CHECKING:
    from pathlib import Path

    from chaff_generator.content.context import RenderContext
    from chaff_generator.renderers.base import Renderer
    from chaff_generator.renderers.documents import SemanticDocument

CAPABILITIES = RendererCapabilities(
    extension="md",
    supports_exact_size=False,
    supports_target_size=True,
    supports_streaming=True,
    semantic_document="ProseDocument",
    size_category="md",
)


def _table_md(columns: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(columns) + " |"]
    lines.append("|" + "|".join("-" * (len(column) + 2) for column in columns) + "|")
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines) + "\n"


def markdown_chunks(document: ProseDocument, context: RenderContext) -> Iterator[str]:
    yield f"# {document.title}\n\n"
    byline = " · ".join(
        part for part in (document.author, document.created_at.strftime("%B %d, %Y")) if part
    )
    if byline:
        yield f"*{byline}*\n\n"
    for section in document.sections:
        if section.heading:
            yield f"## {section.heading}\n\n"
        for block in section.blocks:
            match block:
                case Heading(text=text, level=level):
                    yield f"{'#' * (level + 2)} {text}\n\n"
                case Paragraph(text=text):
                    yield f"{text}\n\n"
                case BulletList(items=items):
                    yield "".join(f"- {item}\n" for item in items) + "\n"
                case NumberedList(items=items):
                    yield "".join(f"{n}. {item}\n" for n, item in enumerate(items, 1)) + "\n"
                case Quote(text=text):
                    yield f"> {text}\n\n"
                case Table(columns=columns, rows=rows):
                    yield _table_md(columns, rows) + "\n"
                case PageBreak():
                    yield "\n---\n\n"
    # Filler sections keep the size approximately on target.
    filler_index = 1
    while True:
        heading = context.template_engine.render_string("{{ word('topics') | title }}")
        yield f"## {heading} (appendix {filler_index})\n\n"
        for _ in range(3):
            yield filler_paragraph(context) + "\n"
        yield "\n"
        filler_index += 1


class MarkdownRenderer:
    id = "md"
    capabilities = CAPABILITIES

    def render(
        self,
        document: SemanticDocument | None,
        destination: Path,
        context: RenderContext,
    ) -> RenderResult:
        doc = document if isinstance(document, ProseDocument) else _fallback_document(context)
        handle, writer = open_writer(destination)
        with handle:
            write_chunks_until(writer, markdown_chunks(doc, context), context.desired_size)
            finish(handle)
        return RenderResult(
            path=destination,
            size=writer.bytes_written,
            renderer_id=self.id,
            template_id=context.template_id,
            sha256=writer.digest_hex,
        )


def _fallback_document(context: RenderContext) -> ProseDocument:
    """No prose template matched: synthesize a minimal titled document."""
    title = context.template_engine.render_string("{{ word('topics') | title }} Notes")
    if context.world.timeline is not None:
        created = context.world.timeline.draw_between(context.rng)
    elif context.world.date_range is not None:
        created = context.world.date_range.start
    else:
        created = date(2025, 6, 15)
    return ProseDocument(
        title=title,
        author=context.world.primary_user.full_name,
        created_at=created,
        sections=[],
    )


def get_renderer(renderer_id: str) -> Renderer:
    if renderer_id != "md":
        raise ValueError(f"markdown module cannot serve renderer id {renderer_id!r}")
    return MarkdownRenderer()
