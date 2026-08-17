"""HTML renderer (approximate size, spec sections 20, 67).

Consumes a :class:`ProseDocument` and emits a standalone HTML page with all
text node content escaped. Filler sections top the file up toward the
desired size.
"""

from __future__ import annotations

from collections.abc import Iterator
from html import escape
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
from chaff_generator.renderers.markdown import _fallback_document
from chaff_generator.renderers.textutil import finish, open_writer

if TYPE_CHECKING:
    from pathlib import Path

    from chaff_generator.content.context import RenderContext
    from chaff_generator.renderers.base import Renderer
    from chaff_generator.renderers.documents import SemanticDocument

CAPABILITIES = RendererCapabilities(
    extension="html",
    supports_exact_size=False,
    supports_target_size=True,
    supports_streaming=True,
    semantic_document="ProseDocument",
    size_category="html",
)


def html_chunks(document: ProseDocument, context: RenderContext) -> Iterator[str]:
    yield (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        f"<title>{escape(document.title)}</title>\n"
        "<style>body{font-family:Georgia,serif;max-width:46rem;margin:2rem auto;"
        "padding:0 1rem;line-height:1.5}h1,h2{color:#222}"
        "table{border-collapse:collapse}td,th{border:1px solid #999;"
        "padding:0.3rem 0.6rem}</style>\n"
        "</head>\n"
        "<body>\n"
    )
    yield f"<h1>{escape(document.title)}</h1>\n"
    byline = " · ".join(
        part for part in (document.author, document.created_at.strftime("%B %d, %Y")) if part
    )
    if byline:
        yield f"<p><em>{escape(byline)}</em></p>\n"
    for section in document.sections:
        if section.heading:
            yield f"<h2>{escape(section.heading)}</h2>\n"
        for block in section.blocks:
            match block:
                case Heading(text=text, level=level):
                    yield f"<h{level + 2}>{escape(text)}</h{level + 2}>\n"
                case Paragraph(text=text):
                    yield f"<p>{escape(text)}</p>\n"
                case BulletList(items=items):
                    inner = "".join(f"<li>{escape(item)}</li>\n" for item in items)
                    yield f"<ul>\n{inner}</ul>\n"
                case NumberedList(items=items):
                    inner = "".join(f"<li>{escape(item)}</li>\n" for item in items)
                    yield f"<ol>\n{inner}</ol>\n"
                case Quote(text=text):
                    yield f"<blockquote>{escape(text)}</blockquote>\n"
                case Table(columns=columns, rows=rows):
                    head = "".join(f"<th>{escape(c)}</th>" for c in columns)
                    body = "".join(
                        "<tr>" + "".join(f"<td>{escape(cell)}</td>" for cell in row) + "</tr>\n"
                        for row in rows
                    )
                    yield f"<table>\n<tr>{head}</tr>\n{body}</table>\n"
                case PageBreak():
                    yield "<hr>\n"
    filler_index = 1
    while True:
        heading = context.template_engine.render_string("{{ word('topics') | title }}")
        yield f"<h2>{escape(heading)} (appendix {filler_index})</h2>\n"
        for _ in range(3):
            yield f"<p>{escape(filler_paragraph(context))}</p>\n"
        filler_index += 1


class HtmlRenderer:
    id = "html"
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
            for chunk in html_chunks(doc, context):
                if writer.bytes_written >= context.desired_size:
                    break
                writer.write(chunk.encode("utf-8"))
            # Closing tags are mandatory: never size-truncated away.
            writer.write(b"</body>\n</html>\n")
            finish(handle)
        return RenderResult(
            path=destination,
            size=writer.bytes_written,
            renderer_id=self.id,
            template_id=context.template_id,
            sha256=writer.digest_hex,
        )


def get_renderer(renderer_id: str) -> Renderer:
    if renderer_id != "html":
        raise ValueError(f"html module cannot serve renderer id {renderer_id!r}")
    return HtmlRenderer()
