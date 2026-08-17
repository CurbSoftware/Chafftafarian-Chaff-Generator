"""The sandboxed Chaff template engine (spec sections 15-16, 14, 51).

Wraps ``jinja2.sandbox.SandboxedEnvironment`` with:

* ``StrictUndefined`` — missing variables fail loudly with a did-you-mean
  suggestion instead of silently emitting malformed documents;
* a constrained Chaff vocabulary (``word``, ``sentence``, ``paragraph``,
  ``integer``, ``money``, dates, ``uuid``, ...) implemented as *closures*
  over the per-file RNG/world — never raw objects exposed to templates;
* controlled recursive expansion of bank entries (depth cap, size cap);
* no loader, so ``import``/``include``/``extends`` cannot resolve; the
  validator additionally rejects those statements in pack templates.

Templates are data, not code: no Python builtins, no attribute traversal
beyond the sandbox's safe-format checks, no filesystem or environment access.
"""

from __future__ import annotations

import difflib
import random
import uuid as uuid_module
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Any

import jinja2
from jinja2 import StrictUndefined, UndefinedError
from jinja2.sandbox import SandboxedEnvironment

from chaff_generator.content import generators as gen
from chaff_generator.core.errors import TemplateError

if TYPE_CHECKING:
    from chaff_generator.content.bank import ChaffBank
    from chaff_generator.content.world import GenerationWorld
    from chaff_generator.templates.models import TemplateDef

#: Maximum recursive expansion depth for bank entries containing Jinja (§14).
MAX_RENDER_DEPTH: int = 5

#: Maximum expanded length of a single bank entry before an error is raised.
MAX_EXPANSION_CHARS: int = 100_000

#: Compiled templates cached per engine instance (bank-sized working set).
_TEMPLATE_CACHE_MAX: int = 4096

_CURRENCY = Decimal("0.01")


def money_value(rng: random.Random, low: float, high: float) -> Decimal:
    """A money amount as a quantized Decimal (never binary-float artifacts)."""
    span = Decimal(str(high)) - Decimal(str(low))
    raw = Decimal(str(low)) + Decimal(rng.random()) * span
    return raw.quantize(_CURRENCY, rounding=ROUND_HALF_UP)


def currency_format(value: object) -> str:
    """Format a number as a currency string with thousands separators."""
    try:
        amount = Decimal(str(value))
    except Exception as exc:
        raise TemplateError(f"currency filter received a non-numeric value: {value!r}") from exc
    return f"{amount:,.2f}"


def date_format(value: object, fmt: str = "%B %d, %Y") -> str:
    """Format a date (or ISO date string) with ``strftime``."""
    target = _parse_template_date(value, "datefmt")
    return target.strftime(fmt)


def _require_str(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise TemplateError(f"{name}() expects a string, got {type(value).__name__}")
    return value


def _require_int(value: object, name: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        if (isinstance(value, float) and value.is_integer()) or (
            isinstance(value, str) and value.lstrip("-").isdigit()
        ):
            value = int(value)
        else:
            raise TemplateError(f"{name}() expects an integer, got {type(value).__name__}")
    if minimum is not None and value < minimum:
        raise TemplateError(f"{name}() expects a value >= {minimum}, got {value}")
    return value


def _parse_template_date(value: object, name: str) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(_require_str(value, name))
    except ValueError as exc:
        raise TemplateError(f"{name}() could not parse date: {value!r}") from exc


class ChaffTemplateEngine:
    """Renders Chaff template strings against one file's deterministic context."""

    def __init__(
        self,
        world: GenerationWorld,
        bank: ChaffBank,
        rng: random.Random,
    ) -> None:
        self._world = world
        self._bank = bank
        self._rng = rng
        self._sentence_tracker = gen.RecentTracker(window=8, max_rerolls=2)
        # Instance-level depth counter: bank entries may themselves contain
        # Jinja that calls back into sentence()/pick(), so recursion is
        # threaded through the engine rather than function parameters.
        self._render_depth: int = 0
        # Compiled-template cache: bank sentences repeat across a large file,
        # so caching turns per-sentence compiles into dict lookups. Bounded;
        # cleared outright when full (sources are bank-sized, so this is rare).
        self._template_cache: dict[str, jinja2.Template] = {}
        self._env = SandboxedEnvironment(
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=False,
        )
        self._env.filters.update(
            {
                "slug": gen.slugify,
                "currency": currency_format,
                "datefmt": date_format,
            }
        )
        self._env.globals.update(self._build_globals())

    # ------------------------------------------------------------------ API

    def render_string(self, source: str, extra: dict[str, Any] | None = None) -> str:
        """Render one Jinja source string with the shared context variables.

        Nested rendering (bank entries containing Jinja) is depth-limited:
        each nested :meth:`render_string` call increments an engine-level
        counter that is capped at :data:`MAX_RENDER_DEPTH`.
        """
        if self._render_depth > MAX_RENDER_DEPTH:
            raise TemplateError(
                f"Recursive template expansion exceeded the depth cap ({MAX_RENDER_DEPTH})"
            )
        template = self._compile(source)
        self._render_depth += 1
        try:
            rendered = template.render(**self._context_variables(extra or {}))
        except UndefinedError as exc:
            raise TemplateError(
                self._undefined_message(source, exc),
                details={"message": str(exc)},
            ) from exc
        except TemplateError:
            raise
        except Exception as exc:
            raise TemplateError(
                f"Template rendering failed: {exc}", details={"source": source[:200]}
            ) from exc
        finally:
            self._render_depth -= 1
        if len(rendered) > MAX_EXPANSION_CHARS:
            raise TemplateError("Template expansion exceeded the size cap")
        return rendered

    def render_template(self, template: TemplateDef, extra: dict[str, Any] | None = None) -> str:
        """Render a template's body as an inline document (debug/preview path)."""
        lines: list[str] = []
        body = template.body
        if "title" in body:
            lines.append(self.render_string(str(body["title"]), extra))
        for key, value in body.items():
            if key == "title":
                continue
            lines.append(self.render_string(str(value), extra))
        return "\n\n".join(lines)

    # ------------------------------------------------------------- internals

    def _compile(self, source: str) -> jinja2.Template:
        cached = self._template_cache.get(source)
        if cached is not None:
            return cached
        try:
            template = self._env.from_string(source)
        except Exception as exc:
            raise TemplateError(
                f"Template syntax error: {exc}", details={"source": source[:200]}
            ) from exc
        if len(self._template_cache) >= _TEMPLATE_CACHE_MAX:
            self._template_cache.clear()
        self._template_cache[source] = template
        return template

    def _context_variables(self, extra: dict[str, Any]) -> dict[str, Any]:
        """Shared variables available to every template in this file's context."""
        rng = self._rng
        world = self._world
        variables: dict[str, Any] = {
            "primary_user": world.primary_user,
            "organization": world.organization,
            "company": world.organization,
        }
        if world.projects:
            variables["project"] = gen.pick(rng, world.projects)
            variables["project_manager"] = (
                world.person_by_id(variables["project"].manager_id) or world.primary_user
            )
        if world.employees:
            variables["person"] = gen.pick(rng, world.employees)
        if world.contacts:
            variables["contact"] = gen.pick(rng, world.contacts)
        if world.clients:
            variables["client"] = gen.pick(rng, world.clients)
        if world.vendors:
            variables["vendor"] = gen.pick(rng, world.vendors)
        if world.meetings:
            variables["meeting"] = gen.pick(rng, world.meetings)
        if world.invoices:
            variables["invoice"] = gen.pick(rng, world.invoices)
        if world.products:
            variables["product"] = gen.pick(rng, world.products)
        variables.update(extra)
        return variables

    def _undefined_message(self, source: str, exc: UndefinedError) -> str:
        """Turn UndefinedError into a helpful message with suggestions (§51)."""
        message = str(exc)
        hint = ""
        extracted = message.split("'")
        if len(extracted) >= 2:
            unknown = extracted[1]
            known = sorted(self._known_variable_names())
            close = difflib.get_close_matches(unknown, known, n=1, cutoff=0.6)
            if close:
                hint = f" — did you mean '{close[0]}'?"
        return f"Unknown template variable: {message}{hint}"

    def _known_variable_names(self) -> list[str]:
        names = [
            "project",
            "person",
            "company",
            "organization",
            "primary_user",
            "contact",
            "client",
            "vendor",
            "meeting",
            "invoice",
            "product",
            "project_manager",
        ]
        return names

    # The constrained Chaff vocabulary --------------------------------------

    def _build_globals(self) -> dict[str, Any]:
        rng = self._rng
        bank = self._bank
        world = self._world
        engine = self

        def word(category: object) -> str:
            return gen.pick(rng, bank.words(_require_str(category, "word")))

        def pick_phrase(category: object) -> str:
            return engine._render_bank_entry(
                gen.pick(rng, bank.phrases(_require_str(category, "pick")))
            )

        def sentence(category: object) -> str:
            pool = bank.sentences(_require_str(category, "sentence"))
            return engine._render_bank_entry(engine._sentence_tracker.pick(rng, pool))

        def paragraph(category: object, count: object = 4) -> str:
            n = _require_int(count, "paragraph", minimum=1)
            pool = bank.sentences(_require_str(category, "paragraph"))
            picked = [
                engine._render_bank_entry(engine._sentence_tracker.pick(rng, pool))
                for _ in range(n)
            ]
            return " ".join(picked)

        def integer(low: object, high: object) -> int:
            lo = _require_int(low, "integer")
            hi = _require_int(high, "integer")
            if hi < lo:
                raise TemplateError(f"integer() range is inverted: {lo} > {hi}")
            return rng.randrange(lo, hi + 1)

        def decimal(low: object, high: object, places: object = 2) -> str:
            lo = float(low) if isinstance(low, (int, float)) else _require_int(low, "decimal")
            hi = float(high) if isinstance(high, (int, float)) else _require_int(high, "decimal")
            digits = _require_int(places, "decimal", minimum=0)
            quant = Decimal(1).scaleb(-digits)
            raw = Decimal(str(lo)) + Decimal(str(rng.random())) * (
                Decimal(str(hi)) - Decimal(str(lo))
            )
            return str(raw.quantize(quant, rounding=ROUND_HALF_UP))

        def money(low: object, high: object) -> str:
            lo_v = low if isinstance(low, (int, float)) else _require_int(low, "money")
            hi_v = high if isinstance(high, (int, float)) else _require_int(high, "money")
            return currency_format(money_value(rng, float(lo_v), float(hi_v)))

        def date_recent(days_back: object = 90) -> str:
            days = _require_int(days_back, "date_recent", minimum=1)
            anchor = world.date_range.end if world.date_range else date.today()
            return (anchor - timedelta(days=rng.randrange(0, days))).isoformat()

        def date_between_helper(start: object, end: object) -> str:
            return gen.date_between(
                rng,
                _parse_template_date(start, "date_between"),
                _parse_template_date(end, "date_between"),
            ).isoformat()

        def uuid() -> str:
            deterministic = uuid_module.UUID(int=rng.getrandbits(128), version=4)
            return str(deterministic)

        def email_address(person: object = None) -> str:
            if person is not None and hasattr(person, "email"):
                return str(person.email)
            local = f"{word('nouns')}.{rng.randrange(100, 999)}".lower()
            return gen.make_email(local, "example.com")

        def phone_number() -> str:
            return gen.make_phone(rng)

        return {
            "word": word,
            "pick": pick_phrase,
            "sentence": sentence,
            "paragraph": paragraph,
            "integer": integer,
            "decimal": decimal,
            "money": money,
            "date_recent": date_recent,
            "date_between": date_between_helper,
            "uuid": uuid,
            "email_address": email_address,
            "phone_number": phone_number,
        }

    def _render_bank_entry(self, entry: str) -> str:
        """Render a bank entry that may itself contain Jinja (§14)."""
        if "{{" not in entry and "{%" not in entry:
            return entry
        return self.render_string(entry)
