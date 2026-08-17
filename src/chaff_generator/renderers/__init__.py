"""File renderers: semantic documents emitted as genuine file formats."""

from __future__ import annotations

from chaff_generator.renderers.registry import RendererRegistry

#: Static registry table: renderer id -> module providing it. Modules are
#: imported lazily on first use so a txt-only run never imports python-pptx.
RENDERER_MODULES: dict[str, str] = {
    "txt": "chaff_generator.renderers.text",
    "log": "chaff_generator.renderers.text",
    "md": "chaff_generator.renderers.markdown",
    "html": "chaff_generator.renderers.html",
    "csv": "chaff_generator.renderers.csv",
    "json": "chaff_generator.renderers.json",
    "xml": "chaff_generator.renderers.xml",
    "eml": "chaff_generator.renderers.email",
    "docx": "chaff_generator.renderers.docx",
    "pdf": "chaff_generator.renderers.pdf",
    "xlsx": "chaff_generator.renderers.xlsx",
    "pptx": "chaff_generator.renderers.pptx",
    "vcf": "chaff_generator.renderers.contact",
    "ics": "chaff_generator.renderers.calendar",
    "dat": "chaff_generator.renderers.payload",
    "dev": "chaff_generator.renderers.devfile",
}


def build_registry() -> RendererRegistry:
    """Create a renderer registry pre-loaded with the module table."""
    return RendererRegistry(RENDERER_MODULES)
