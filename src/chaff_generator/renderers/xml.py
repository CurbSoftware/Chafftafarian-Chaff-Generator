"""XML renderer (approximate size, spec sections 20, 67).

Manual streaming writer (no ElementTree tree building) with ``saxutils``
escaping; the root element is always closed so size top-up can never leave
the document malformed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from xml.sax.saxutils import escape, quoteattr

from chaff_generator.renderers.base import RendererCapabilities, RenderResult
from chaff_generator.renderers.tabular import columnar_records
from chaff_generator.renderers.textutil import finish, open_writer

if TYPE_CHECKING:
    from pathlib import Path

    from chaff_generator.content.context import RenderContext
    from chaff_generator.renderers.base import Renderer
    from chaff_generator.renderers.documents import SemanticDocument

CAPABILITIES = RendererCapabilities(
    extension="xml",
    supports_exact_size=False,
    supports_target_size=True,
    supports_streaming=True,
    semantic_document=None,
    size_category="xml",
)


class XmlRenderer:
    id = "xml"
    capabilities = CAPABILITIES

    def render(
        self,
        document: SemanticDocument | None,
        destination: Path,
        context: RenderContext,
    ) -> RenderResult:
        title, columns, rows = columnar_records(document, context)
        handle, writer = open_writer(destination)
        with handle:
            writer.write(
                (
                    f'<?xml version="1.0" encoding="UTF-8"?>\n<records type={quoteattr(title)}>\n'
                ).encode()
            )
            for row in rows:
                writer.write(b"  <record>\n")
                for name, cell in zip(columns, row, strict=False):
                    writer.write(
                        (
                            f"    <field name={quoteattr(str(name))}>{escape(str(cell))}</field>\n"
                        ).encode()
                    )
                writer.write(b"  </record>\n")
                if writer.bytes_written >= context.desired_size:
                    break
            writer.write(b"</records>\n")
            finish(handle)
        return RenderResult(
            path=destination,
            size=writer.bytes_written,
            renderer_id=self.id,
            template_id=context.template_id,
            sha256=writer.digest_hex,
        )


def get_renderer(renderer_id: str) -> Renderer:
    if renderer_id != "xml":
        raise ValueError(f"xml module cannot serve renderer id {renderer_id!r}")
    return XmlRenderer()
