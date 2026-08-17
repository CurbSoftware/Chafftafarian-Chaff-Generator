"""Size expression parsing and formatting (spec section 8)."""

from __future__ import annotations

import pytest

from chaff_generator.core.errors import ConfigurationError
from chaff_generator.core.size import format_size, parse_percent, parse_size


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1048576", 1_048_576),
        ("1 MB", 1_000_000),
        ("10 MB", 10_000_000),
        ("1.5 GiB", 1_610_612_736),
        ("500 KiB", 512_000),
        ("500k", 500_000),
        ("2 TB", 2_000_000_000_000),
        ("2 TiB", 2_199_023_255_552),
        (" 3   gb ", 3_000_000_000),
        ("1M", 1_000_000),
        ("7 MiB", 7_340_032),
        ("0", 0),
    ],
)
def test_parse_size_table(text: str, expected: int) -> None:
    assert parse_size(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "-5 MB",
        "banana",
        "1.2.3 MB",
        "",
        "  ",
        "9 EiB",  # over the 2**63-1 guard
        "99999999999999999999999",
    ],
)
def test_parse_size_rejects(text: str) -> None:
    with pytest.raises(ConfigurationError):
        parse_size(text)


def test_parse_size_mantissa_is_decimal_not_float() -> None:
    # 0.1 GiB would be lossy through binary float; Decimal keeps it exact.
    assert parse_size("0.1 GiB") == int(1024**3 * 0.1)
    assert parse_size("0.1 GiB") == 107_374_182  # 0.1 * 2**30, truncated


def test_format_size_binary() -> None:
    assert format_size(0) == "0 B"
    assert format_size(1023) == "1023 B"
    assert format_size(1024) == "1 KiB"
    assert format_size(1_610_612_736) == "1.5 GiB"


def test_format_size_decimal() -> None:
    assert format_size(1_000_000, binary=False) == "1 MB"


def test_parse_percent() -> None:
    assert parse_percent("50") == 50
    assert parse_percent("12.5") == 12.5
    assert parse_percent("50%") == 50


@pytest.mark.parametrize("value", ["0", "-1", "100.01", "abc"])
def test_parse_percent_rejects(value: str) -> None:
    with pytest.raises(ConfigurationError):
        parse_percent(value)
