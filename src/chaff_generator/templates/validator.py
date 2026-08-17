"""Template validation: schema, Jinja compilation, and banned statements.

Used by ``chaff packs validate`` and the ChaffBank GUI page so broken
templates fail at pack-validation time, not mid-generation.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from jinja2 import Environment, StrictUndefined
from jinja2.exceptions import TemplateSyntaxError

from chaff_generator.content import generators as gen
from chaff_generator.content.template_engine import currency_format, date_format
from chaff_generator.templates.models import TemplateDef

if TYPE_CHECKING:
    from chaff_generator.templates.models import TemplateRegistry

#: Statements that must never appear in pack templates (§16).
_BANNED_STATEMENT_RE = re.compile(
    r"{%-?\s*(import|include|extends|from|with|autoescape|set\s+_[a-z])\b", re.IGNORECASE
)

#: Calls into dunder/dangerous attribute space anywhere in a template.
_BANNED_DUNDER_RE = re.compile(r"__\w+__")


@dataclass
class ValidationIssue:
    template_id: str
    message: str
    severity: str = "error"  # "error" | "warning"


@dataclass
class TemplateValidationReport:
    template_id: str
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)


def _iter_template_strings(body: dict[str, Any]) -> Iterator[tuple[str, str]]:
    """Yield (label, source) for every Jinja-bearing string in a body."""

    def walk(value: Any, label: str) -> Iterator[tuple[str, str]]:
        if isinstance(value, str):
            yield label, value
        elif isinstance(value, list):
            for index, item in enumerate(value):
                yield from walk(item, f"{label}[{index}]")
        elif isinstance(value, dict):
            for key, item in value.items():
                yield from walk(item, f"{label}.{key}")

    yield from walk(body, "body")


def _compile_environment() -> Environment:
    """A plain environment carrying the same filters as the Chaff engine.

    Used only to compile-check template sources; rendering itself always goes
    through the sandboxed :class:`~chaff_generator.content.template_engine.\
ChaffTemplateEngine`.
    """
    env = Environment(undefined=StrictUndefined)
    env.filters.update(
        {
            "slug": gen.slugify,
            "currency": currency_format,
            "datefmt": date_format,
        }
    )
    return env


def validate_template(template: TemplateDef) -> TemplateValidationReport:
    """Validate one template definition beyond structural schema checks."""
    report = TemplateValidationReport(template_id=template.id)
    compile_env = _compile_environment()

    for label, source in _iter_template_strings(template.body):
        if _BANNED_DUNDER_RE.search(source):
            report.issues.append(
                ValidationIssue(
                    template.id,
                    f"{label}: dunder references are not allowed in templates",
                )
            )
        for statement in _BANNED_STATEMENT_RE.finditer(source):
            report.issues.append(
                ValidationIssue(
                    template.id,
                    f"{label}: banned template statement {statement.group(0)!r}",
                )
            )
        try:
            compile_env.compile(source)
        except TemplateSyntaxError as exc:
            report.issues.append(
                ValidationIssue(
                    template.id,
                    f"{label}: Jinja syntax error at line {exc.lineno}: {exc.message}",
                )
            )

    if template.kind == "prose" and not template.render_targets:
        report.issues.append(
            ValidationIssue(template.id, "prose template has no render targets", severity="warning")
        )
    return report


def validate_registry_templates(registry: TemplateRegistry) -> list[TemplateValidationReport]:
    """Validate every template in a registry."""
    return [validate_template(template) for template in registry.all()]
