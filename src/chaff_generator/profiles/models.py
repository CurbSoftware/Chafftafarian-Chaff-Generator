"""Profile models (spec sections 23, 25, 69).

Profiles are data, not code: they control format weights, content domains,
directory layout, per-format size ranges, and default average file sizes used
for file-count estimation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from chaff_generator.core.errors import ConfigurationError
from chaff_generator.core.models import LayoutMode
from chaff_generator.core.size import parse_size


@dataclass(frozen=True)
class SizeRange:
    min_bytes: int
    max_bytes: int

    def __post_init__(self) -> None:
        if self.min_bytes < 0 or self.max_bytes < self.min_bytes:
            raise ValueError(f"Invalid size range: {self.min_bytes}..{self.max_bytes}")


@dataclass(frozen=True)
class Profile:
    id: str
    name: str
    description: str
    directory_layout: LayoutMode
    format_weights: dict[str, int]
    content_domains: dict[str, int]
    size_profile: dict[str, SizeRange]
    avg_file_size_bytes: int
    payload_default: bool = False


#: Default realistic size ranges per format id (spec section 23), used when a
#: profile does not override them.
DEFAULT_SIZE_RANGES: dict[str, SizeRange] = {
    "txt": SizeRange(1 << 10, 20 << 20),
    "log": SizeRange(4 << 10, 30 << 20),
    "md": SizeRange(1 << 10, 2 << 20),
    "html": SizeRange(2 << 10, 4 << 20),
    "csv": SizeRange(5 << 10, 100 << 20),
    "json": SizeRange(5 << 10, 100 << 20),
    "xml": SizeRange(5 << 10, 60 << 20),
    "eml": SizeRange(2 << 10, 5 << 20),
    "docx": SizeRange(10 << 10, 3 << 20),
    "pdf": SizeRange(10 << 10, 15 << 20),
    "xlsx": SizeRange(10 << 10, 30 << 20),
    "pptx": SizeRange(50 << 10, 10 << 20),
    "vcf": SizeRange(1 << 10, 256 << 10),
    "ics": SizeRange(1 << 10, 512 << 10),
    "dat": SizeRange(1 << 20, 4 << 30),
    "dev": SizeRange(1 << 10, 1 << 20),
}

#: Average file sizes used for file-count estimation when a profile does not
#: specify one (deliberately lower than the max so estimates stay realistic).
DEFAULT_AVG_SIZES: dict[str, int] = {
    "txt": 60 << 10,
    "log": 200 << 10,
    "md": 12 << 10,
    "html": 30 << 10,
    "csv": 400 << 10,
    "json": 400 << 10,
    "xml": 250 << 10,
    "eml": 30 << 10,
    "docx": 120 << 10,
    "pdf": 300 << 10,
    "xlsx": 150 << 10,
    "pptx": 400 << 10,
    "vcf": 8 << 10,
    "ics": 12 << 10,
    "dat": 64 << 20,
    "dev": 8 << 10,
}


def _parse_size_value(value: Any, label: str) -> int:
    """Accept either a plain byte count or a size expression like ``1 MiB``."""
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    try:
        return parse_size(str(value))
    except Exception as exc:
        raise ConfigurationError(f"Invalid size for {label}: {value!r}") from exc


def parse_size_ranges(raw: dict[str, Any] | None) -> dict[str, SizeRange]:
    """Parse a ``{format: {min: "..", max: ".."}}`` mapping into SizeRanges."""
    result: dict[str, SizeRange] = {}
    for format_id, entry in (raw or {}).items():
        if isinstance(entry, dict):
            label = f"size_profile.{format_id}"
            result[str(format_id)] = SizeRange(
                _parse_size_value(entry["min"], f"{label}.min"),
                _parse_size_value(entry["max"], f"{label}.max"),
            )
    return result
