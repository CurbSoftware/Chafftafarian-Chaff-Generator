"""CSV renderer (approximate size, spec sections 20, 67).

Renders tabular/record documents with the stdlib csv writer in binary mode
with ``lineterminator="\\n"`` so files are byte-identical across OSes.
"""

from __future__ import annotations

import csv
from typing import TYPE_CHECKING

from chaff_generator.renderers.base import RendererCapabilities, RenderResult
from chaff_generator.renderers.tabular import columnar_records
from chaff_generator.renderers.textutil import finish, open_writer

if TYPE_CHECKING:
    from pathlib import Path

    from chaff_generator.content.context import RenderContext
    from chaff_generator.core.hashing import HashingWriter
    from chaff_generator.renderers.base import Renderer
    from chaff_generator.renderers.documents import SemanticDocument

CAPABILITIES = RendererCapabilities(
    extension="csv",
    supports_exact_size=False,
    supports_target_size=True,
    supports_streaming=True,
    semantic_document="TabularDocument",
    size_category="csv",
)


class _RowAdapter:
    """Adapts the csv writer's str writes onto the hashing binary writer."""

    def __init__(self, writer: HashingWriter) -> None:
        self._writer = writer

    def write(self, text: str) -> int:
        data = text.encode("utf-8")
        self._writer.write(data)
        return len(data)


class CsvRenderer:
    id = "csv"
    capabilities = CAPABILITIES

    def render(
        self,
        document: SemanticDocument | None,
        destination: Path,
        context: RenderContext,
    ) -> RenderResult:
        _title, columns, rows = columnar_records(document, context)
        handle, writer = open_writer(destination)
        with handle:
            csv_writer = csv.writer(_RowAdapter(writer), lineterminator="\n")
            csv_writer.writerow(columns)
            for row in rows:
                csv_writer.writerow([str(cell) for cell in row])
                if writer.bytes_written >= context.desired_size:
                    break
            finish(handle)
        return RenderResult(
            path=destination,
            size=writer.bytes_written,
            renderer_id=self.id,
            template_id=context.template_id,
            sha256=writer.digest_hex,
        )


def get_renderer(renderer_id: str) -> Renderer:
    if renderer_id != "csv":
        raise ValueError(f"csv module cannot serve renderer id {renderer_id!r}")
    return CsvRenderer()
