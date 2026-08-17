"""DAT renderer — deterministic streamed storage payloads (spec section 22).

Chunks are derived from ``shake_256("chaff-payload:v1:{seed}:{chunk}")``, so
a payload is byte-reproducible from its per-file seed alone, is written
incrementally (never held in memory), and is **real data on disk** — no
truncate/seek/sparse tricks. Every chunk is hashed as it is written.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from chaff_generator.renderers.base import RendererCapabilities, RenderResult
from chaff_generator.renderers.textutil import finish, open_writer

if TYPE_CHECKING:
    from pathlib import Path

    from chaff_generator.content.context import RenderContext
    from chaff_generator.renderers.base import Renderer
    from chaff_generator.renderers.documents import SemanticDocument

CAPABILITIES = RendererCapabilities(
    extension="dat",
    supports_exact_size=True,
    supports_target_size=True,
    supports_streaming=True,
    semantic_document=None,
    size_category="payload",
)

#: Payload chunk size: big enough to stream fast, small enough that the
#: final partial chunk wastes little.
CHUNK_BYTES = 1 << 20  # 1 MiB


class PayloadRenderer:
    id = "dat"
    capabilities = CAPABILITIES

    def render(
        self,
        document: SemanticDocument | None,
        destination: Path,
        context: RenderContext,
    ) -> RenderResult:
        seed = context.file_seed
        size = max(0, context.desired_size)

        handle, writer = open_writer(destination)
        with handle:
            written = 0
            chunk_index = 0
            while written < size:
                piece = _chunk(seed, chunk_index)
                take = min(len(piece), size - written)
                writer.write(piece[:take])
                written += take
                chunk_index += 1
            finish(handle)

        return RenderResult(
            path=destination,
            size=writer.bytes_written,
            renderer_id=self.id,
            template_id=context.template_id,
            sha256=writer.digest_hex,
        )


def _chunk(seed: int, chunk_index: int, length: int = CHUNK_BYTES) -> bytes:
    """Deterministic chunk bytes from the payload's identity (spec section 22)."""
    stream = hashlib.shake_256(f"chaff-payload:v1:{seed}:{chunk_index}".encode())
    return stream.digest(length)


def get_renderer(renderer_id: str) -> Renderer:
    if renderer_id != "dat":
        raise ValueError(f"payload module cannot serve renderer id {renderer_id!r}")
    return PayloadRenderer()
