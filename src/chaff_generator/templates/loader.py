"""Load template YAML files from a ChaffBank pack directory.

Templates live at ``<pack>/templates/<kind>/*.yaml`` and are parsed with
``yaml.safe_load`` only. Every file must carry ``id`` and ``kind``; unknown
keys or malformed bodies raise :class:`TemplateError` at load time so broken
packs fail loudly before generation starts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from chaff_generator.core.errors import TemplateError
from chaff_generator.templates.models import (
    PROSE_RENDER_TARGETS,
    TEMPLATE_KINDS,
    TemplateDef,
    TemplateRegistry,
    allowed_section_keys,
    template_body_schema,
)


def _validate_string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TemplateError(f"{label} must be a list of strings")
    return value


def _validate_prose_body(template_id: str, body: dict[str, Any]) -> None:
    sections = body.get("sections")
    if not isinstance(sections, list) or not sections:
        raise TemplateError(f"{template_id}: 'sections' must be a non-empty list")
    for position, section in enumerate(sections):
        label = f"{template_id}: sections[{position}]"
        if not isinstance(section, dict):
            raise TemplateError(f"{label} must be a mapping")
        unknown = set(section) - set(allowed_section_keys())
        if unknown:
            raise TemplateError(f"{label} has unknown keys: {sorted(unknown)}")
        for key in ("paragraphs", "bullets", "numbered"):
            if key in section:
                _validate_string_list(section[key], f"{label}.{key}")
        if "table" in section:
            table = section["table"]
            if not isinstance(table, dict) or not {"columns", "rows"} <= set(table):
                raise TemplateError(f"{label}.table must have 'columns' and 'rows'")
            _validate_string_list(table["columns"], f"{label}.table.columns")
            if not isinstance(table["rows"], list) or not all(
                isinstance(row, list) for row in table["rows"]
            ):
                raise TemplateError(f"{label}.table.rows must be a list of lists")


def _validate_body(template_id: str, kind: str, body: dict[str, Any]) -> None:
    allowed, required = template_body_schema(kind)
    unknown = set(body) - set(allowed)
    if unknown:
        raise TemplateError(f"{template_id}: unknown body keys {sorted(unknown)}")
    missing = set(required) - set(body)
    if missing:
        raise TemplateError(f"{template_id}: missing required keys {sorted(missing)}")

    if kind == "prose":
        _validate_prose_body(template_id, body)
    elif kind == "email":
        _validate_string_list(body["body_paragraphs"], f"{template_id}.body_paragraphs")
    elif kind in {"tabular", "record"}:
        _validate_string_list(body["columns"], f"{template_id}.columns")
        if "rows" in body and not isinstance(body["rows"], list):
            raise TemplateError(f"{template_id}.rows must be a list")
    elif kind == "presentation":
        slides = body["slides"]
        if not isinstance(slides, list) or not slides:
            raise TemplateError(f"{template_id}: 'slides' must be a non-empty list")
        for position, slide in enumerate(slides):
            if not isinstance(slide, dict):
                raise TemplateError(f"{template_id}.slides[{position}] must be a mapping")


def parse_template_file(path: Path) -> TemplateDef:
    """Parse and structurally validate one template YAML file."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise TemplateError(f"{path.name}: invalid YAML — {exc}") from exc
    if not isinstance(data, dict):
        raise TemplateError(f"{path.name}: template file must be a mapping")

    template_id = data.get("id")
    kind = data.get("kind")
    if not isinstance(template_id, str) or not isinstance(kind, str):
        raise TemplateError(f"{path.name}: 'id' and 'kind' are required strings")
    if kind not in TEMPLATE_KINDS:
        raise TemplateError(f"{path.name}: unknown kind {kind!r}")

    body = data.get("body")
    if not isinstance(body, dict):
        raise TemplateError(f"{path.name}: 'body' mapping is required")
    _validate_body(template_id, kind, body)

    render_targets_raw = data.get("render_targets") or []
    if kind == "prose":
        render_targets = tuple(render_targets_raw) or tuple(PROSE_RENDER_TARGETS)
        invalid = set(render_targets) - PROSE_RENDER_TARGETS
        if invalid:
            raise TemplateError(f"{path.name}: invalid render_targets {sorted(invalid)}")
    else:
        render_targets = ()

    try:
        return TemplateDef(
            id=template_id,
            kind=kind,
            body=body,
            description=str(data.get("description", "")),
            render_targets=render_targets,
            domains=tuple(str(item) for item in (data.get("domains") or [])),
        )
    except ValueError as exc:
        raise TemplateError(f"{path.name}: {exc}") from exc


def load_templates(pack_dir: Path) -> TemplateRegistry:
    """Load every template under ``<pack_dir>/templates/``."""
    registry = TemplateRegistry()
    templates_root = pack_dir / "templates"
    if not templates_root.is_dir():
        return registry
    for kind_dir in sorted(templates_root.iterdir()):
        if not kind_dir.is_dir() or kind_dir.name not in TEMPLATE_KINDS:
            continue
        for file in sorted(kind_dir.glob("*.yaml")):
            template = parse_template_file(file)
            if template.kind != kind_dir.name:
                raise TemplateError(
                    f"{file.name}: kind {template.kind!r} does not match "
                    f"directory {kind_dir.name!r}"
                )
            registry.add(template)
    return registry
