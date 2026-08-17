"""Sandboxed template engine: helpers, strictness, and security (spec 15-16, 51)."""

from __future__ import annotations

import random

import pytest

from chaff_generator.content.bank import ChaffBank
from chaff_generator.content.template_engine import ChaffTemplateEngine
from chaff_generator.content.world import GenerationWorld
from chaff_generator.core.errors import TemplateError


@pytest.fixture()
def engine(world: GenerationWorld, default_bank: ChaffBank) -> ChaffTemplateEngine:
    return ChaffTemplateEngine(world, default_bank, random.Random(2026))


class TestVocabulary:
    def test_word_and_sentence(self, engine: ChaffTemplateEngine) -> None:
        rendered = engine.render_string("{{ word('nouns') }} {{ sentence('business') }}")
        assert " " in rendered
        assert "{{" not in rendered

    def test_paragraph_join(self, engine: ChaffTemplateEngine) -> None:
        rendered = engine.render_string("{{ paragraph('business', 3) }}")
        assert rendered.count(". ") >= 1 or rendered.endswith(".")

    def test_integer_bounds(self, engine: ChaffTemplateEngine) -> None:
        values = {engine.render_string("{{ integer(3, 5) }}") for _ in range(30)}
        assert values <= {"3", "4", "5"}

    def test_money_format(self, engine: ChaffTemplateEngine) -> None:
        rendered = engine.render_string("{{ money(100000, 200000) }}")
        assert "," in rendered and "." in rendered

    def test_uuid_valid_and_deterministic(self, engine: ChaffTemplateEngine) -> None:
        first = engine.render_string("{{ uuid() }}")
        assert len(first) == 36
        other_engine = ChaffTemplateEngine(engine._world, engine._bank, random.Random(2026))
        assert other_engine.render_string("{{ uuid() }}") == first

    def test_deterministic_rerun(self, engine: ChaffTemplateEngine) -> None:
        source = "{{ sentence('technical') }} {{ word('topics') }}"
        twin = ChaffTemplateEngine(engine._world, engine._bank, random.Random(2026))
        assert engine.render_string(source) == twin.render_string(source)

    def test_filters(self, engine: ChaffTemplateEngine) -> None:
        assert engine.render_string("{{ 'Hello World' | slug }}") == "hello-world"
        assert engine.render_string("{{ 1234.5 | currency }}") == "1,234.50"
        assert engine.render_string("{{ '2025-06-15' | datefmt('%Y/%m/%d') }}") == "2025/06/15"

    def test_context_variables_resolve(self, engine: ChaffTemplateEngine) -> None:
        rendered = engine.render_string(
            "{{ primary_user.full_name }} {{ project.code }} {{ organization.name }}"
        )
        assert rendered.strip()


class TestStrictness:
    def test_unknown_variable_names_template(self, engine: ChaffTemplateEngine) -> None:
        with pytest.raises(TemplateError, match=r"projekt|proj"):
            engine.render_string("{{ projekt.name }}")

    def test_unknown_bank_category(self, engine: ChaffTemplateEngine) -> None:
        with pytest.raises(TemplateError):
            engine.render_string("{{ word('nonexistent') }}")

    def test_bad_argument_types(self, engine: ChaffTemplateEngine) -> None:
        with pytest.raises(TemplateError):
            engine.render_string("{{ word(42) }}")
        with pytest.raises(TemplateError):
            engine.render_string("{{ integer('x', 3) }}")

    def test_syntax_error(self, engine: ChaffTemplateEngine) -> None:
        with pytest.raises(TemplateError, match="syntax"):
            engine.render_string("{{ sentence('business') }")


class TestSecurity:
    @pytest.mark.parametrize(
        "attack",
        [
            "{{ ''.__class__ }}",
            "{{ ''.__class__.__mro__ }}",
            "{{ config.__class__ }}",
            "{% import os %}",
            "{% include 'x.html' %}",
            "{% extends 'base.html' %}",
            "{{ person.__dict__ }}",
            "{{ word.__globals__ }}",
        ],
    )
    def test_sandbox_attacks_rejected(self, engine: ChaffTemplateEngine, attack: str) -> None:
        with pytest.raises((TemplateError, Exception)):
            engine.render_string(attack)

    def test_no_loader_attribute(self, engine: ChaffTemplateEngine) -> None:
        assert engine._env.loader is None

    def test_globals_are_closures_not_objects(self, engine: ChaffTemplateEngine) -> None:
        for name, value in engine._env.globals.items():
            assert callable(value), name  # every global is a function closure


class TestRecursionControl:
    def test_depth_cap(self, default_bank: ChaffBank, world: GenerationWorld) -> None:
        """A bank entry that re-calls sentence() must hit the depth cap, not loop."""

        class BombBank:
            """Minimal bank stub whose every sentence re-triggers rendering."""

            def sentences(self, category: str) -> tuple[str, ...]:
                return ("{{ sentence('business') }}",)

            def phrases(self, category: str) -> tuple[str, ...]:
                return ("{{ pick('greetings') }}",)

            def words(self, category: str) -> tuple[str, ...]:
                return ("loop",)

        engine = ChaffTemplateEngine(world, BombBank(), random.Random(1))  # type: ignore[arg-type]
        with pytest.raises(TemplateError, match="depth"):
            engine.render_string("{{ sentence('business') }}")

    def test_depth_counter_resets(self, world: GenerationWorld, default_bank: ChaffBank) -> None:
        engine = ChaffTemplateEngine(world, default_bank, random.Random(1))
        for _ in range(10):
            engine.render_string("{{ word('nouns') }}")
        assert engine._render_depth == 0
