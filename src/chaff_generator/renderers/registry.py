"""Lazy renderer registry (spec section 20).

Maps renderer ids to module dotted-paths and imports on first use, keeping
CLI startup fast and avoiding heavy office libraries for text-only runs.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

from chaff_generator.core.errors import RendererError

if TYPE_CHECKING:
    from chaff_generator.renderers.base import Renderer


class RendererRegistry:
    def __init__(self, module_table: dict[str, str]) -> None:
        self._module_table = dict(module_table)
        self._instances: dict[str, Renderer] = {}

    def register(self, renderer_id: str, module_path: str) -> None:
        """Add or replace a renderer mapping (extension point for plugins)."""
        self._module_table[renderer_id] = module_path
        self._instances.pop(renderer_id, None)

    def has(self, renderer_id: str) -> bool:
        return renderer_id in self._module_table

    def ids(self) -> list[str]:
        return sorted(self._module_table)

    def get(self, renderer_id: str) -> Renderer:
        """Return the renderer instance, importing its module on first use."""
        if renderer_id not in self._instances:
            module_path = self._module_table.get(renderer_id)
            if module_path is None:
                raise RendererError(f"Unknown renderer: {renderer_id}")
            try:
                module = importlib.import_module(module_path)
            except ImportError as exc:
                raise RendererError(
                    f"Renderer module failed to import: {module_path}: {exc}"
                ) from exc
            factory = getattr(module, "get_renderer", None)
            if factory is None:
                raise RendererError(f"Renderer module has no get_renderer(): {module_path}")
            self._instances[renderer_id] = factory(renderer_id)
        return self._instances[renderer_id]
