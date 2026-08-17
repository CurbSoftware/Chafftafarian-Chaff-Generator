"""Renderer protocol, capabilities, and results (spec section 20)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from chaff_generator.content.context import RenderContext
    from chaff_generator.renderers.documents import SemanticDocument


@dataclass(frozen=True)
class RendererCapabilities:
    """What a renderer can do; drives planning and the finalizer loop."""

    extension: str
    #: Can land on an exact byte count (usable as an exact-size finalizer).
    supports_exact_size: bool
    #: Can aim at a target size approximately.
    supports_target_size: bool
    #: Streams output in bounded memory.
    supports_streaming: bool
    #: Which semantic document type this renderer consumes (None = self-generating).
    semantic_document: str | None
    #: Key into the profile's size_profile for default size ranges.
    size_category: str


@dataclass
class RenderResult:
    path: Path
    size: int
    renderer_id: str
    template_id: str | None = None
    #: Digest of the file as written; when None the engine re-hashes the file.
    sha256: str | None = None
    warnings: list[str] = field(default_factory=list)


@runtime_checkable
class Renderer(Protocol):
    """Shared protocol implemented by every file renderer."""

    id: str
    capabilities: RendererCapabilities

    def render(
        self,
        document: SemanticDocument | None,
        destination: Path,
        context: RenderContext,
    ) -> RenderResult: ...


def write_bytes_exact(destination: Path, produce: bytes) -> int:
    """Write a small in-memory payload; returns the byte count."""
    destination.write_bytes(produce)
    return len(produce)
