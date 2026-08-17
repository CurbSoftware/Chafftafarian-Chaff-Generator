"""Developer-artifact renderer (approximate size, spec section 67).

Generates benign, realistic-looking development snippets — Python modules,
SQL scripts, service configs, project metadata, containerfiles — whose names
and constants come from the synthetic world. Content is chosen by the final
filename's extension (the engine renders to ``<name>.<ext>.chaff-partial``,
so the real suffix is ``destination.suffixes[0]``). Comment lines top the
file up toward the desired size.
"""

from __future__ import annotations

import random
from collections.abc import Iterator
from typing import TYPE_CHECKING

from chaff_generator.content import generators as gen
from chaff_generator.renderers.base import RendererCapabilities, RenderResult
from chaff_generator.renderers.textutil import finish, open_writer

if TYPE_CHECKING:
    from pathlib import Path

    from chaff_generator.content.context import RenderContext
    from chaff_generator.renderers.base import Renderer
    from chaff_generator.renderers.documents import SemanticDocument

CAPABILITIES = RendererCapabilities(
    extension="py",
    supports_exact_size=False,
    supports_target_size=True,
    supports_streaming=True,
    semantic_document=None,
    size_category="dev",
)


def _snippet_kind(destination: Path, context: RenderContext) -> str:
    """Pick the snippet flavor from the *final* filename.

    The engine renders to ``<final-name>.chaff-partial``; the true suffix (or
    a stem like ``Dockerfile`` with no suffix) is provided via
    ``context.extra`` by the planner.
    """
    final_suffix = str(context.extra.get("final_suffix", "")).lower()
    if final_suffix:
        return final_suffix
    stem = str(context.extra.get("final_stem", "") or destination.name).lower()
    if "dockerfile" in stem or "containerfile" in stem:
        return "dockerfile"
    suffixes = destination.suffixes
    if len(suffixes) > 1:  # e.g. "utils.py.chaff-partial" -> "py"
        return suffixes[0].lstrip(".").lower()
    return "txt"


def _sql_quote(value: str) -> str:
    return value.replace("'", "''")


def _module_name(context: RenderContext, rng: random.Random) -> str:
    word = gen.pick(rng, context.bank.words("nouns")).replace(" ", "_").lower()
    return f"{word}_service"


def _python_chunks(context: RenderContext) -> Iterator[str]:
    rng = context.rng
    world = context.world
    project = world.any_project(rng)
    module = _module_name(context, rng)
    owner = world.any_person(rng)
    yield (
        f'"""{module}: generated harness for the {project.name} effort.\n'
        "\n"
        f"Contact: {owner.full_name} <{owner.email}>\n"
        '"""\n\n'
        "from __future__ import annotations\n\n"
        "import logging\n"
        "from dataclasses import dataclass\n\n"
        "logger = logging.getLogger(__name__)\n\n\n"
    )
    yield (
        "@dataclass(frozen=True)\n"
        f"class {module.title().replace('_', '')}Config:\n"
        f'    """Runtime settings (project {project.code})."""\n\n'
        "    service_name: str\n"
        "    batch_size: int = 50\n"
        "    dry_run: bool = False\n\n\n"
    )
    tech = gen.pick(rng, context.bank.words("technologies"))
    yield (
        f"def summarize_batches(items: list[str], batch_size: int = 50) -> list[int]:\n"
        f'    """Split incoming {tech} payloads into measured batches."""\n'
        "    sizes: list[int] = []\n"
        "    for start in range(0, len(items), batch_size):\n"
        "        sizes.append(min(batch_size, len(items) - start))\n"
        "    return sizes\n\n\n"
    )
    yield (
        "def main() -> None:\n"
        '    logging.basicConfig(level="INFO")\n'
        f'    logger.info("starting {module} for project {project.code}")\n'
        "\n"
        '\nif __name__ == "__main__":\n'
        "    main()\n"
    )
    index = 1
    while True:
        yield f"# review note {index}: coordinate with the platform team before merging.\n"
        index += 1


def _sql_chunks(context: RenderContext) -> Iterator[str]:
    rng = context.rng
    yield (
        "-- Seeded reference data for integration environments.\n"
        "-- All rows are synthetic; no production data is included.\n\n"
        "BEGIN;\n\n"
        "CREATE TABLE IF NOT EXISTS vendor_orders (\n"
        "    order_id     TEXT PRIMARY KEY,\n"
        "    vendor       TEXT NOT NULL,\n"
        "    item         TEXT NOT NULL,\n"
        "    quantity     INTEGER NOT NULL,\n"
        "    unit_price   NUMERIC(10, 2) NOT NULL,\n"
        "    placed_on    DATE NOT NULL\n"
        ");\n\n"
    )
    index = 1
    while True:
        vendor = (
            gen.pick(rng, context.world.vendors).name if context.world.vendors else "Example Vendor"
        )
        product = gen.pick(rng, context.world.products)
        day = (
            context.world.timeline.draw_between(rng).isoformat()
            if context.world.timeline
            else "2025-06-15"
        )
        yield (
            "INSERT INTO vendor_orders "
            "(order_id, vendor, item, quantity, unit_price, placed_on)\n"
            f"VALUES ('ORD-{index:06d}', '{_sql_quote(vendor)}', "
            f"'{_sql_quote(product.name)}', {rng.randrange(1, 20)}, "
            f"{product.unit_price}, DATE '{day}');\n"
        )
        index += 1


def _yaml_chunks(context: RenderContext) -> Iterator[str]:
    rng = context.rng
    tech = gen.pick(rng, context.bank.words("technologies")).lower().replace(" ", "-")
    project = context.world.any_project(rng)
    yield (
        f"# Deployment profile for the {project.name} pipeline.\n"
        f"service: {tech}-pipeline\n"
        'version: "3"\n\n'
        "server:\n"
        f"  port: {rng.randrange(1024, 65535)}\n"
        "  workers: 4\n"
        "  timeout_seconds: 30\n\n"
        "logging:\n"
        '  level: "info"\n'
        "  format: " + '"%(asctime)s %(levelname)s %(name)s %(message)s"\n\n'
        "features:\n"
        "  retries: true\n"
        "  cache:\n"
        f"    enabled: {str(rng.random() < 0.5).lower()}\n"
        f"    ttl_seconds: {rng.randrange(60, 3600)}\n"
    )
    index = 1
    while True:
        endpoint = gen.pick(rng, context.bank.words("topics")).replace(" ", "_").lower()
        yield f'  endpoint_{index}: "/api/v1/{endpoint}"\n'
        index += 1


def _toml_chunks(context: RenderContext) -> Iterator[str]:
    rng = context.rng
    project = context.world.any_project(rng)
    slug = gen.slugify(project.name)
    yield (
        f"# Project metadata for {project.name}.\n"
        "[project]\n"
        f'name = "{slug}"\n'
        f'version = "{rng.randrange(0, 3)}.{rng.randrange(1, 12)}.{rng.randrange(0, 10)}"\n'
        'requires-python = ">=3.12"\n\n'
        "[dependencies]\n"
    )
    while True:
        tech = gen.pick(rng, context.bank.words("technologies")).lower().replace(" ", "-")
        yield f'{tech} = "^{rng.randrange(1, 5)}.{rng.randrange(0, 20)}"\n'


def _dockerfile_chunks(context: RenderContext) -> Iterator[str]:
    rng = context.rng
    tech = gen.pick(rng, context.bank.words("technologies")).lower().replace(" ", "-")
    yield (
        f"# {tech.title()} runtime image for local development.\n"
        "FROM python:3.12-slim\n\n"
        "WORKDIR /app\n\n"
        "COPY requirements.txt ./\n"
        "RUN pip install --no-cache-dir -r requirements.txt\n\n"
        "COPY . .\n\n"
        f"ENV SERVICE_ROLE={tech}\n"
        f"ENV LOG_LEVEL=info\n\n"
        f"EXPOSE {rng.randrange(1024, 65535)}\n\n"
        'CMD ["python", "-m", "app.main"]\n'
    )
    index = 1
    while True:
        yield f"# build note {index}: rebuild after dependency changes.\n"
        index += 1


def _text_chunks(context: RenderContext) -> Iterator[str]:
    yield from _python_chunks(context)


_KIND_TABLE = {
    "py": _python_chunks,
    "sql": _sql_chunks,
    "yaml": _yaml_chunks,
    "yml": _yaml_chunks,
    "toml": _toml_chunks,
    "dockerfile": _dockerfile_chunks,
}


class DevFileRenderer:
    id = "dev"
    capabilities = CAPABILITIES

    def render(
        self,
        document: SemanticDocument | None,
        destination: Path,
        context: RenderContext,
    ) -> RenderResult:
        kind = _snippet_kind(destination, context)
        factory = _KIND_TABLE.get(kind, _text_chunks)
        handle, writer = open_writer(destination)
        with handle:
            for chunk in factory(context):
                if writer.bytes_written >= context.desired_size:
                    break
                writer.write(chunk.encode("utf-8"))
            finish(handle)
        return RenderResult(
            path=destination,
            size=writer.bytes_written,
            renderer_id=self.id,
            template_id=context.template_id,
            sha256=writer.digest_hex,
        )


def get_renderer(renderer_id: str) -> Renderer:
    if renderer_id != "dev":
        raise ValueError(f"devfile module cannot serve renderer id {renderer_id!r}")
    return DevFileRenderer()
