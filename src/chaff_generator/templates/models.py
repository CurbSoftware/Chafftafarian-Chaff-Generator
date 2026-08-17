"""Template definition models (spec sections 32-33).

A template is identified as ``<kind>.<name>`` (e.g. ``prose.project_status``).
Its ``body`` is a validated plain mapping whose string fields are Jinja
source rendered through the sandboxed Chaff template engine. Per-kind body
schemas are enforced by :func:`template_body_schema` and the validator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Final

TEMPLATE_KINDS: Final[frozenset[str]] = frozenset(
    {"prose", "email", "tabular", "presentation", "record", "calendar", "contact"}
)

#: prose templates may target any of these renderers via `render_targets`.
PROSE_RENDER_TARGETS: Final[frozenset[str]] = frozenset({"txt", "md", "html", "docx", "pdf"})


@dataclass(frozen=True)
class TemplateDef:
    id: str
    kind: str
    body: dict[str, Any]
    description: str = ""
    render_targets: tuple[str, ...] = field(default=())
    domains: tuple[str, ...] = field(default=())

    def __post_init__(self) -> None:
        if self.kind not in TEMPLATE_KINDS:
            raise ValueError(f"Unknown template kind: {self.kind!r}")
        expected_prefix = f"{self.kind}."
        if not self.id.startswith(expected_prefix):
            raise ValueError(f"Template id {self.id!r} must start with {expected_prefix!r}")


class TemplateRegistry:
    """In-memory set of templates loaded from a pack."""

    def __init__(self) -> None:
        self._templates: dict[str, TemplateDef] = {}

    def add(self, template: TemplateDef) -> None:
        if template.id in self._templates:
            raise ValueError(f"Duplicate template id: {template.id}")
        self._templates[template.id] = template

    def get(self, template_id: str) -> TemplateDef | None:
        return self._templates.get(template_id)

    def require(self, template_id: str) -> TemplateDef:
        template = self._templates.get(template_id)
        if template is None:
            raise KeyError(f"Unknown template: {template_id}")
        return template

    def for_kind(self, kind: str) -> list[TemplateDef]:
        return [t for t in self._templates.values() if t.kind == kind]

    def all(self) -> list[TemplateDef]:
        return list(self._templates.values())

    def __len__(self) -> int:
        return len(self._templates)


# ---------------------------------------------------------------------------
# Body schemas: the set of allowed keys per template kind, plus which are
# required. Values are validated structurally by the loader (str/list/dict).

_PROSE_SECTION_KEYS: Final[frozenset[str]] = frozenset(
    {"heading", "paragraphs", "bullets", "numbered", "table", "quote", "page_break"}
)

_BODY_SCHEMAS: Final[dict[str, tuple[frozenset[str], frozenset[str]]]] = {
    "prose": (frozenset({"title", "author", "sections"}), frozenset({"title", "sections"})),
    "email": (
        frozenset(
            {
                "subject",
                "from_name",
                "to_name",
                "category",
                "body_paragraphs",
                "signature",
                "attachments",
            }
        ),
        frozenset({"subject", "body_paragraphs"}),
    ),
    "tabular": (
        frozenset({"sheet_title", "columns", "rows", "notes"}),
        frozenset({"columns"}),
    ),
    "presentation": (
        frozenset({"title", "subtitle", "slides"}),
        frozenset({"title", "slides"}),
    ),
    "record": (
        frozenset({"record_type", "columns", "row_count"}),
        frozenset({"record_type", "columns"}),
    ),
    "calendar": (frozenset({"event_count"}), frozenset()),
    "contact": (frozenset({"contact_count"}), frozenset()),
}


def template_body_schema(kind: str) -> tuple[frozenset[str], frozenset[str]]:
    """Return (allowed_keys, required_keys) for a template kind's body."""
    return _BODY_SCHEMAS[kind]


def allowed_section_keys() -> frozenset[str]:
    """Allowed keys inside a prose template's section entries."""
    return _PROSE_SECTION_KEYS
