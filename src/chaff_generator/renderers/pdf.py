"""PDF renderer — reportlab platypus over ProseDocument (spec sections 66, 74).

``rl_config.invariant = 1`` pins document IDs and drops timestamps, so PDFs
*are* byte-deterministic under the same seed — unlike the OOXML formats.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import reportlab.rl_config
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    SimpleDocTemplate,
    Spacer,
    TableStyle,
)
from reportlab.platypus import (
    Paragraph as FlowableParagraph,
)
from reportlab.platypus import (
    Table as FlowableTable,
)

from chaff_generator.core.hashing import hash_file
from chaff_generator.renderers.base import RendererCapabilities, RenderResult
from chaff_generator.renderers.docx import ensure_prose_volume

reportlab.rl_config.invariant = 1

if TYPE_CHECKING:
    from pathlib import Path

    from chaff_generator.content.context import RenderContext
    from chaff_generator.renderers.base import Renderer
    from chaff_generator.renderers.documents import Block, SemanticDocument, Table

CAPABILITIES = RendererCapabilities(
    extension="pdf",
    supports_exact_size=False,
    supports_target_size=True,
    supports_streaming=False,
    semantic_document="prose",
    size_category="document",
)

#: PDF text compresses; aim high so landed size lands near the draw.
_BODY_FRACTION = 1.15

_MARGIN = 0.9 * inch


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _page_number(canvas, doc) -> None:  # type: ignore[no-untyped-def]
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.grey)
    canvas.drawRightString(letter[0] - _MARGIN, 0.5 * inch, f"Page {doc.page}")
    canvas.restoreState()


class PdfRenderer:
    id = "pdf"
    capabilities = CAPABILITIES

    def render(
        self,
        document: SemanticDocument | None,
        destination: Path,
        context: RenderContext,
    ) -> RenderResult:
        if document is None:
            from chaff_generator.renderers.markdown import _fallback_document

            document = _fallback_document(context)
        from chaff_generator.renderers.documents import ProseDocument

        assert isinstance(document, ProseDocument)
        ensure_prose_volume(document, context, int(context.desired_size * _BODY_FRACTION))

        styles = getSampleStyleSheet()
        story: list[object] = [FlowableParagraph(_escape(document.title), styles["Title"])]
        story.append(
            FlowableParagraph(
                f"{_escape(document.author)} &middot; {document.created_at.isoformat()}",
                styles["Normal"],
            )
        )
        story.append(Spacer(1, 12))

        for section in document.sections:
            if section.heading:
                story.append(FlowableParagraph(_escape(section.heading), styles["Heading1"]))
            for block in section.blocks:
                story.extend(self._block_flowables(block, styles))

        builder = SimpleDocTemplate(
            str(destination),
            pagesize=letter,
            leftMargin=_MARGIN,
            rightMargin=_MARGIN,
            topMargin=_MARGIN,
            bottomMargin=_MARGIN,
            title=document.title,
            author=document.author,
            creator=f"Chaff Generator {context.app_version}",
        )
        builder.build(
            story,
            onFirstPage=_page_number,
            onLaterPages=_page_number,
        )

        size = destination.stat().st_size
        return RenderResult(
            path=destination,
            size=size,
            renderer_id=self.id,
            template_id=context.template_id,
            sha256=hash_file(destination),
        )

    # ---------------------------------------------------------------- internals

    def _block_flowables(self, block: Block, styles) -> list[object]:  # type: ignore[no-untyped-def]
        from chaff_generator.renderers.documents import (
            BulletList,
            Heading,
            NumberedList,
            Paragraph,
            Quote,
            Table,
        )
        from chaff_generator.renderers.documents import (
            PageBreak as DocPageBreak,
        )

        if isinstance(block, Heading):
            name = "Heading2" if block.level <= 2 else "Heading3"
            return [FlowableParagraph(_escape(block.text), styles[name])]
        if isinstance(block, Paragraph):
            return [FlowableParagraph(_escape(block.text), styles["BodyText"])]
        if isinstance(block, Quote):
            return [FlowableParagraph(_escape(block.text), styles["Italic"])]
        if isinstance(block, BulletList):
            return [FlowableParagraph(_escape(item), styles["Bullet"]) for item in block.items]
        if isinstance(block, NumberedList):
            return [
                FlowableParagraph(f"{index}. {_escape(item)}", styles["BodyText"])
                for index, item in enumerate(block.items, start=1)
            ]
        if isinstance(block, Table):
            return [self._table(block)]
        if isinstance(block, DocPageBreak):
            return [PageBreak()]
        return []

    def _table(self, block: Table) -> FlowableTable:
        rows = [[_escape(str(col)) for col in block.columns]]
        rows.extend([_escape(str(cell)) for cell in row] for row in block.rows)
        usable = letter[0] - 2 * _MARGIN
        width = usable / max(len(block.columns), 1)
        table = FlowableTable(rows, colWidths=[width] * max(len(block.columns), 1))
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DDDDDD")),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                ]
            )
        )
        return table


def get_renderer(renderer_id: str) -> Renderer:
    if renderer_id != "pdf":
        raise ValueError(f"pdf module cannot serve renderer id {renderer_id!r}")
    return PdfRenderer()
