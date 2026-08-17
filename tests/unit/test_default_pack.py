"""The shipped default pack: every template validates, parses, and renders.

This is the pack quality gate (spec sections 32-33, 51): a broken bank or
template file must fail here, never mid-generation.
"""

from __future__ import annotations

import random

from chaff_generator.content.bank import ChaffBank
from chaff_generator.content.template_engine import ChaffTemplateEngine
from chaff_generator.content.world import GenerationWorld
from chaff_generator.templates.models import TEMPLATE_KINDS
from chaff_generator.templates.validator import validate_registry_templates


def test_all_templates_validate(default_bank: ChaffBank) -> None:
    reports = validate_registry_templates(default_bank.templates())
    errors = [i for r in reports for i in r.issues if i.severity == "error"]
    assert not errors, "\n".join(f"{i.template_id}: {i.message}" for i in errors)


def test_template_counts_and_kinds(default_bank: ChaffBank) -> None:
    registry = default_bank.templates()
    assert len(registry) >= 40
    kinds = {t.kind for t in registry.all()}
    assert kinds == {"prose", "email", "tabular", "presentation", "record"}
    for kind in ("prose", "email", "tabular", "presentation", "record"):
        assert kind in TEMPLATE_KINDS
        assert registry.for_kind(kind), f"no templates for kind {kind}"


def test_every_template_renders_three_times(
    default_bank: ChaffBank, world: GenerationWorld
) -> None:
    """Three seeds each, so flaky mixes of banks/entities surface here."""
    for template in default_bank.templates().all():
        for attempt in range(3):
            engine = ChaffTemplateEngine(world, default_bank, random.Random(700 + attempt))
            output = engine.render_template(template)
            assert output.strip(), f"{template.id} rendered empty"
            assert "{{" not in output and "{%" not in output, f"{template.id} left unrendered Jinja"


def test_pack_yaml_metadata(default_bank: ChaffBank) -> None:
    manifest = default_bank.manifest
    assert manifest.language == "en"
    assert manifest.version
    assert "Census" in manifest.attribution or "attribution" in manifest.attribution.lower()
