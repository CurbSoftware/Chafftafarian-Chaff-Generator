"""JSON renderer (approximate size, spec sections 20, 67).

Streams a JSON array one record per line so large files never materialize
in memory. The array is always closed — size top-up never truncates the
structure into invalid JSON.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from chaff_generator.renderers.base import RendererCapabilities, RenderResult
from chaff_generator.renderers.tabular import object_records
from chaff_generator.renderers.textutil import finish, open_writer

if TYPE_CHECKING:
    from pathlib import Path

    from chaff_generator.content.context import RenderContext
    from chaff_generator.renderers.base import Renderer
    from chaff_generator.renderers.documents import SemanticDocument

CAPABILITIES = RendererCapabilities(
    extension="json",
    supports_exact_size=False,
    supports_target_size=True,
    supports_streaming=True,
    semantic_document=None,
    size_category="json",
)


class JsonRenderer:
    id = "json"
    capabilities = CAPABILITIES

    def render(
        self,
        document: SemanticDocument | None,
        destination: Path,
        context: RenderContext,
    ) -> RenderResult:
        _title, records = object_records(document, context)
        handle, writer = open_writer(destination)
        with handle:
            writer.write(b"[\n")
            first = True
            for record in records:
                if not first and writer.bytes_written >= context.desired_size:
                    break
                prefix = "  " if first else ",\n  "
                line = json.dumps(record, ensure_ascii=False, default=str)
                writer.write((prefix + line).encode("utf-8"))
                first = False
            writer.write(b"\n]\n")
            finish(handle)
        return RenderResult(
            path=destination,
            size=writer.bytes_written,
            renderer_id=self.id,
            template_id=context.template_id,
            sha256=writer.digest_hex,
        )


def get_renderer(renderer_id: str) -> Renderer:
    if renderer_id != "json":
        raise ValueError(f"json module cannot serve renderer id {renderer_id!r}")
    return JsonRenderer()
