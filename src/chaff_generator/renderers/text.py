"""Plain-text renderer (exact-size capable, spec sections 20, 26, 67).

Consumes a :class:`ProseDocument` when the planner matched a prose template,
otherwise self-generates paragraphs from the pack's sentence banks. Either
way the file lands on *exactly* ``desired_size`` bytes: content is streamed
until the target is reached, then the final line is cut on a UTF-8 boundary
and space-padded.
"""

from __future__ import annotations

from collections.abc import Iterator
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
from chaff_generator.renderers.textutil import finish, open_writer, write_chunks_exact

if TYPE_CHECKING:
    from pathlib import Path

    from chaff_generator.content.context import RenderContext
    from chaff_generator.renderers.base import Renderer
    from chaff_generator.renderers.documents import SemanticDocument

CAPABILITIES = RendererCapabilities(
    extension="txt",
    supports_exact_size=True,
    supports_target_size=True,
    supports_streaming=True,
    semantic_document="ProseDocument",
    size_category="txt",
)


def _format_table(columns: list[str], rows: list[list[str]]) -> str:
    widths = [len(column) for column in columns]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    lines = ["  ".join(column.ljust(widths[i]) for i, column in enumerate(columns))]
    lines.append("  ".join("-" * width for width in widths))
    for row in rows:
        lines.append("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)))
    return "\n".join(lines) + "\n\n"


def prose_chunks(document: ProseDocument, context: RenderContext) -> Iterator[str]:
    """Yield the document as text chunks, then filler paragraphs forever."""
    if document.title:
        yield document.title + "\n"
        if document.author:
            yield f"Prepared by {document.author}\n"
        yield "=" * min(len(document.title), 72) + "\n\n"
    for section in document.sections:
        if section.heading:
            underline = "-" * min(len(section.heading), 72)
            yield f"{section.heading}\n{underline}\n\n"
        for block in section.blocks:
            match block:
                case Heading(text=text, level=level):
                    yield f"{text.upper()}\n\n" if level <= 1 else f"{text}\n\n"
                case Paragraph(text=text):
                    yield f"{text}\n\n"
                case BulletList(items=items):
                    yield "".join(f"  - {item}\n" for item in items) + "\n"
                case NumberedList(items=items):
                    yield "".join(f"  {n}. {item}\n" for n, item in enumerate(items, 1)) + "\n"
                case Quote(text=text):
                    yield f'  "{text}"\n\n'
                case Table(columns=columns, rows=rows):
                    yield _format_table(columns, rows)
                case PageBreak():
                    yield "-" * 40 + "\n\n"
    while True:
        yield filler_paragraph(context) + "\n\n"


def _self_chunks(context: RenderContext) -> Iterator[str]:
    header = context.template_engine.render_string("{{ word('topics') | title }} Notes")
    yield header + "\n" + "-" * min(len(header), 72) + "\n\n"
    while True:
        yield filler_paragraph(context) + "\n\n"


class TextRenderer:
    id = "txt"
    capabilities = CAPABILITIES

    def render(
        self,
        document: SemanticDocument | None,
        destination: Path,
        context: RenderContext,
    ) -> RenderResult:
        if isinstance(document, ProseDocument):
            chunks = prose_chunks(document, context)
        else:
            chunks = _self_chunks(context)
        handle, writer = open_writer(destination)
        with handle:
            write_chunks_exact(writer, chunks, context.desired_size)
            finish(handle)
        return RenderResult(
            path=destination,
            size=writer.bytes_written,
            renderer_id=self.id,
            template_id=context.template_id,
            sha256=writer.digest_hex,
        )


def get_renderer(renderer_id: str) -> Renderer:
    if renderer_id != "txt":
        raise ValueError(f"text module cannot serve renderer id {renderer_id!r}")
    return TextRenderer()
