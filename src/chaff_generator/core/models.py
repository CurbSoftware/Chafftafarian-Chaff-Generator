"""Job configuration models, enums, and (de)serialization.

The same :class:`GenerationConfig` is loadable from the GUI, the CLI, and
JSON/YAML preset files (spec section 7). Plain dataclasses plus explicit
validation — no heavy validation dependency.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields, is_dataclass
from datetime import date
from decimal import Decimal
from enum import Enum, StrEnum
from pathlib import Path
from typing import Any

import yaml

from chaff_generator.core.errors import ConfigurationError
from chaff_generator.core.size import parse_size

SCHEMA_VERSION = 1


class TargetMode(StrEnum):
    EXACT = "exact"
    PERCENT_FREE = "percent_free"
    FILL_UNTIL_RESERVE = "fill_until_reserve"


class LayoutMode(StrEnum):
    FLAT = "flat"
    SIMPLE = "simple"
    REALISTIC = "realistic"


class CompletionAction(StrEnum):
    KEEP = "keep"
    DELETE = "delete"
    TRASH = "trash"


class RunStatus(StrEnum):
    PLANNING = "planning"
    RUNNING = "running"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"


class Verdict(StrEnum):
    INTACT = "INTACT"
    MISSING = "MISSING"
    SIZE_MISMATCH = "SIZE_MISMATCH"
    HASH_MISMATCH = "HASH_MISMATCH"
    UNREADABLE = "UNREADABLE"


@dataclass
class DateRange:
    start: date
    end: date

    def __post_init__(self) -> None:
        if self.start > self.end:
            raise ConfigurationError(f"date_range start ({self.start}) is after end ({self.end})")


@dataclass
class TargetSpec:
    path: Path
    mode: TargetMode
    amount: int | None = None  # bytes, for EXACT
    percent: Decimal | None = None  # for PERCENT_FREE
    reserve: int = 2 * 10**9  # bytes kept free at all times

    def __post_init__(self) -> None:
        if self.mode is TargetMode.EXACT and (self.amount is None or self.amount <= 0):
            raise ConfigurationError("EXACT mode requires a positive amount")
        if self.mode is TargetMode.PERCENT_FREE and self.percent is None:
            raise ConfigurationError("PERCENT_FREE mode requires a percent value")
        if self.reserve < 0:
            raise ConfigurationError("reserve cannot be negative")


@dataclass
class FileTypeSetting:
    enabled: bool
    weight: int = 10

    def __post_init__(self) -> None:
        if self.weight < 0:
            raise ConfigurationError("file type weight cannot be negative")


@dataclass
class IntegritySettings:
    create_manifest: bool = True
    algorithm: str = "sha256"


@dataclass
class GenerationConfig:
    schema_version: int
    target: TargetSpec
    profile: str = "mixed"
    seed: int = 0
    date_range: DateRange = field(
        default_factory=lambda: DateRange(date(2023, 1, 1), date(2026, 8, 1))
    )
    directory_layout: LayoutMode = LayoutMode.REALISTIC
    file_types: dict[str, FileTypeSetting] = field(default_factory=dict)
    integrity: IntegritySettings = field(default_factory=IntegritySettings)
    completion: CompletionAction = CompletionAction.KEEP
    active_pack: str | None = None


@dataclass
class GenerationResult:
    run_id: str
    run_root: Path
    status: RunStatus
    files_created: int
    bytes_written: int
    duration_s: float
    throughput_bps: float
    manifest_path: Path | None
    warnings: list[str]
    error: str | None


@dataclass
class PreflightSummary:
    target_path: Path
    free_bytes: int
    requested_bytes: int | None
    projected_remaining_bytes: int | None
    estimated_file_count: int
    formats: list[str]
    profile_id: str
    seed: int
    completion: CompletionAction
    manifest_enabled: bool
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Serialization


def _to_builtin(obj: Any) -> Any:
    if is_dataclass(obj) and not isinstance(obj, type):
        result: dict[str, Any] = {}
        for f in fields(obj):
            result[f.name] = _to_builtin(getattr(obj, f.name))
        return result
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {key: _to_builtin(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_builtin(item) for item in obj]
    return obj


def config_to_dict(config: GenerationConfig) -> dict[str, Any]:
    """Convert a config to a plain dict suitable for YAML/JSON output."""
    return _to_builtin(config)


def dump_config(config: GenerationConfig, path: Path) -> None:
    """Write a config preset to ``path`` (format chosen by suffix)."""
    data = config_to_dict(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() in {".yaml", ".yml"}:
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    else:
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _parse_date(value: Any, label: str) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ConfigurationError(f"Invalid {label}: {value!r}") from exc


def _parse_target(data: dict[str, Any]) -> TargetSpec:
    raw_path = data.get("path")
    if not isinstance(raw_path, str) or not raw_path:
        raise ConfigurationError("target.path is required")
    mode_raw = data.get("mode", "exact")
    try:
        mode = TargetMode(str(mode_raw))
    except ValueError as exc:
        raise ConfigurationError(f"Unknown target mode: {mode_raw!r}") from exc

    amount: int | None = None
    if data.get("amount") is not None:
        amount = (
            data["amount"] if isinstance(data["amount"], int) else parse_size(str(data["amount"]))
        )

    percent: Decimal | None = None
    if data.get("percent") is not None:
        percent = Decimal(str(data["percent"]))

    reserve_raw = data.get("reserve", 2 * 10**9)
    reserve = reserve_raw if isinstance(reserve_raw, int) else parse_size(str(reserve_raw))

    return TargetSpec(
        path=Path(raw_path), mode=mode, amount=amount, percent=percent, reserve=reserve
    )


def dict_to_config(data: dict[str, Any]) -> GenerationConfig:
    """Build and validate a :class:`GenerationConfig` from a plain mapping."""
    if not isinstance(data, dict):
        raise ConfigurationError("Configuration root must be a mapping")

    version = data.get("schema_version", SCHEMA_VERSION)
    if version != SCHEMA_VERSION:
        raise ConfigurationError(
            f"Unsupported schema_version {version!r}; expected {SCHEMA_VERSION}"
        )

    target_data = data.get("target")
    if not isinstance(target_data, dict):
        raise ConfigurationError("target section is required")
    target = _parse_target(target_data)

    date_data = data.get("date_range") or {}
    date_range = DateRange(
        start=_parse_date(date_data.get("start", "2023-01-01"), "date_range.start"),
        end=_parse_date(date_data.get("end", "2026-08-01"), "date_range.end"),
    )

    layout_raw = data.get("directory_layout", "realistic")
    try:
        layout = LayoutMode(str(layout_raw))
    except ValueError as exc:
        raise ConfigurationError(f"Unknown directory layout: {layout_raw!r}") from exc

    file_types: dict[str, FileTypeSetting] = {}
    for name, setting in (data.get("file_types") or {}).items():
        if isinstance(setting, bool):
            file_types[str(name)] = FileTypeSetting(enabled=setting)
        elif isinstance(setting, dict):
            file_types[str(name)] = FileTypeSetting(
                enabled=bool(setting.get("enabled", True)),
                weight=int(setting.get("weight", 10)),
            )
        else:
            raise ConfigurationError(f"Invalid file_types entry for {name!r}")

    completion_raw = data.get("completion", "keep")
    try:
        completion = CompletionAction(str(completion_raw))
    except ValueError as exc:
        raise ConfigurationError(f"Unknown completion action: {completion_raw!r}") from exc

    integrity_data = data.get("integrity") or {}
    integrity = IntegritySettings(
        create_manifest=bool(integrity_data.get("create_manifest", True)),
        algorithm=str(integrity_data.get("algorithm", "sha256")),
    )

    return GenerationConfig(
        schema_version=SCHEMA_VERSION,
        target=target,
        profile=str(data.get("profile", "mixed")),
        seed=int(data.get("seed", 0)),
        date_range=date_range,
        directory_layout=layout,
        file_types=file_types,
        integrity=integrity,
        completion=completion,
        active_pack=data.get("active_pack"),
    )


def load_config(path: Path) -> GenerationConfig:
    """Load a config preset from a YAML or JSON file."""
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text) if path.suffix.lower() in {".yaml", ".yml"} else json.loads(text)
    return dict_to_config(data)
