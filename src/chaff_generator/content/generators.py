"""Deterministic primitives for building synthetic content.

Every function takes an isolated ``random.Random`` instance — there is no
process-global RNG anywhere in the package (spec section 11).
"""

from __future__ import annotations

import random
import re
import string
import uuid
from collections import deque
from collections.abc import Sequence
from datetime import date, timedelta
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from chaff_generator.content.bank import ChaffBank

T = TypeVar("T")

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def pick[T](rng: random.Random, seq: Sequence[T]) -> T:
    """Pick one element uniformly."""
    if not seq:
        raise ValueError("pick() called with an empty sequence")
    return seq[rng.randrange(len(seq))]


class RecentTracker:
    """Repetition control (spec section 63).

    Biases selection away from recently used items without globally banning
    repeats: a few rerolls are attempted before accepting a repeat.
    """

    def __init__(self, window: int = 12, max_rerolls: int = 3) -> None:
        self._recent: deque[object] = deque(maxlen=window)
        self._max_rerolls = max_rerolls

    def pick(self, rng: random.Random, seq: Sequence[T]) -> T:
        if not seq:
            raise ValueError("pick() called with an empty sequence")
        choice = pick(rng, seq)
        for _ in range(self._max_rerolls):
            if choice not in self._recent or len(seq) <= len(self._recent):
                break
            choice = pick(rng, seq)
        self._recent.append(choice)
        return choice

    def reset(self) -> None:
        self._recent.clear()


def slugify(text: str) -> str:
    """Convert text to a lowercase slug usable in filenames and identifiers."""
    slug = _SLUG_RE.sub("-", text.lower()).strip("-")
    return slug or "item"


def make_email(local: str, domain: str) -> str:
    """Build a synthetic, non-routable email address."""
    cleaned = re.sub(r"[^a-z0-9._-]", "", local.lower()) or "user"
    return f"{cleaned}@{domain}"


def make_phone(rng: random.Random) -> str:
    """Build a plausible but fake phone number (555 exchange, fictional range)."""
    return f"({rng.randrange(200, 999)}) 555-{rng.randrange(1000, 9999):04d}"


def make_company_name(rng: random.Random, bank: ChaffBank) -> str:
    """Compose a company name from the pack's word banks."""
    adjective = pick(rng, bank.words("adjectives")).title()
    noun = pick(rng, bank.words("nouns")).title()
    word1 = pick(rng, bank.entity_lines("company_words"))
    word2 = pick(rng, bank.entity_lines("company_words"))
    patterns: list[str] = [
        f"{adjective} {noun}",
        f"{word1} {noun}",
        f"{word1} {word2}",
    ]
    cities = bank.entity_lines("cities")
    if cities:
        patterns.append(f"{noun} of {pick(rng, cities)}")
    return patterns[rng.randrange(len(patterns))] or "Northstar Group"


def make_project_name(rng: random.Random, bank: ChaffBank) -> str:
    """Compose a project name from the pack's word banks."""
    noun = pick(rng, bank.words("nouns")).title()
    verb = pick(rng, bank.words("verbs")).title()
    patterns = [
        f"{noun} {verb} Initiative",
        f"{pick(rng, bank.words('technologies'))} Platform Refresh",
        f"{pick(rng, bank.words('topics')).title()} Program",
        f"{pick(rng, bank.entity_lines('company_words'))} Migration",
    ]
    return patterns[rng.randrange(len(patterns))] or "Systems Upgrade"


def make_street_address(rng: random.Random, bank: ChaffBank) -> str:
    """Compose a synthetic street address from harvested street names."""
    number = rng.randrange(100, 9800)
    streets = bank.entity_lines("street_names")
    street = pick(rng, streets) if streets else "Main Street"
    return f"{number} {street}"


def make_city(rng: random.Random, bank: ChaffBank) -> str:
    """Pick a city from the pack's harvested cities list."""
    cities = bank.entity_lines("cities")
    return pick(rng, cities) if cities else "Springfield"


def date_between(rng: random.Random, start: date, end: date) -> date:
    """Pick a date uniformly within [start, end]."""
    if start > end:
        raise ValueError(f"date_between: start {start} after end {end}")
    span = (end - start).days
    return start + timedelta(days=rng.randrange(span + 1))


def date_after(rng: random.Random, anchor: date, min_days: int, max_days: int) -> date:
    """Pick a date ``min_days..max_days`` after ``anchor`` (timeline consistency, §64)."""
    return anchor + timedelta(days=rng.randrange(min_days, max_days + 1))


def make_id(prefix: str, rng: random.Random | None = None) -> str:
    """Build a short deterministic-ish identifier; UUIDs when no rng is given."""
    if rng is None:
        return str(uuid.uuid4())
    alphabet = string.ascii_lowercase + string.digits
    return f"{prefix}_{rng.randrange(100, 999)}{''.join(rng.choice(alphabet) for _ in range(4))}"
