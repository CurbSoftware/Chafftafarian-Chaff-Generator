"""Human-readable size parsing and formatting.

All quantities are handled as integer bytes internally. Fractional inputs are
parsed with :class:`decimal.Decimal` so no floating-point error can creep into
byte counts (spec section 10).
"""

from __future__ import annotations

import re
from decimal import Decimal, DecimalException, InvalidOperation
from typing import Final

from chaff_generator.core.errors import ConfigurationError

# Decimal (power-of-1000) and binary (power-of-1024) multipliers.
_UNIT_FACTORS: Final[dict[str, int]] = {
    "": 1,
    "b": 1,
    "kb": 10**3,
    "k": 10**3,
    "mb": 10**6,
    "m": 10**6,
    "gb": 10**9,
    "g": 10**9,
    "tb": 10**12,
    "t": 10**12,
    "kib": 1 << 10,
    "mib": 1 << 20,
    "gib": 1 << 30,
    "tib": 1 << 40,
}

_SIZE_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>[a-zA-Z]*)\s*$"
)

MAX_BYTES: Final[int] = 2**63 - 1


def parse_size(text: str) -> int:
    """Parse a human-readable size string into an integer byte count.

    Accepts decimal units (KB, MB, GB, TB), binary units (KiB, MiB, GiB, TiB),
    bare unit letters (K, M, G, T), plain byte counts, and fractional values
    such as ``"1.5 GiB"``. Raises :class:`ConfigurationError` for anything
    unparseable, negative, or beyond ``2**63 - 1`` bytes.
    """
    if not isinstance(text, str) or not text.strip():
        raise ConfigurationError(f"Invalid size value: {text!r}")

    match = _SIZE_RE.match(text)
    if match is None:
        raise ConfigurationError(f"Invalid size value: {text!r}")

    unit = match.group("unit").lower()
    if unit not in _UNIT_FACTORS:
        raise ConfigurationError(f"Unknown size unit in {text!r}: {match.group('unit')!r}")

    try:
        value = Decimal(match.group("value"))
    except InvalidOperation as exc:  # pragma: no cover - regex guarantees digits
        raise ConfigurationError(f"Invalid size value: {text!r}") from exc

    factor = Decimal(_UNIT_FACTORS[unit])
    try:
        total = value * factor
    except DecimalException as exc:  # pragma: no cover - defensive
        raise ConfigurationError(f"Invalid size value: {text!r}") from exc

    if total < 0:
        raise ConfigurationError(f"Size cannot be negative: {text!r}")

    bytes_ = int(total.to_integral_value())
    if bytes_ > MAX_BYTES:
        raise ConfigurationError(f"Size exceeds the supported maximum: {text!r}")
    return bytes_


def format_size(nbytes: int, *, binary: bool = True) -> str:
    """Format an integer byte count for display.

    Uses binary units (KiB/MiB/GiB/TiB) by default; pass ``binary=False`` for
    decimal units (KB/MB/GB/TB). Values below the smallest unit render as
    plain bytes.
    """
    if nbytes < 0:
        raise ValueError("nbytes must be non-negative")
    threshold = 1024 if binary else 1000
    if nbytes < threshold:
        return f"{nbytes} B"

    units: list[tuple[str, int]] = (
        [("KiB", 1 << 10), ("MiB", 1 << 20), ("GiB", 1 << 30), ("TiB", 1 << 40)]
        if binary
        else [("KB", 10**3), ("MB", 10**6), ("GB", 10**9), ("TB", 10**12)]
    )

    chosen_unit, chosen_factor = units[0]
    for unit, factor in units[1:]:
        if nbytes >= factor:
            chosen_unit, chosen_factor = unit, factor

    value = Decimal(nbytes) / Decimal(chosen_factor)
    text = f"{value:.1f}".rstrip("0").rstrip(".")
    return f"{text} {chosen_unit}"


def parse_percent(text: str) -> Decimal:
    """Parse a percentage value such as ``"75"`` or ``"75%"`` into a Decimal."""
    cleaned = text.strip().rstrip("%").strip()
    try:
        value = Decimal(cleaned)
    except InvalidOperation as exc:
        raise ConfigurationError(f"Invalid percentage value: {text!r}") from exc
    if value <= 0 or value > 100:
        raise ConfigurationError(f"Percentage must be in (0, 100]: {text!r}")
    return value
