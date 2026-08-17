"""Manifest, journal, and run discovery readers (spec section 35).

Readers are defensive: a journal truncated mid-line by a crash is read up to
the last complete record, and manifests with unknown schema versions are
refused with a clear error rather than mis-verified.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from chaff_generator.core.errors import ManifestError
from chaff_generator.manifest.models import (
    MANIFEST_FILENAME,
    MANIFEST_SCHEMA_VERSION,
    RUN_MARKER_FILENAME,
    ChaffManifest,
    FileRecord,
)


def read_manifest(path: Path) -> ChaffManifest:
    """Load and validate a manifest file."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ManifestError(f"Cannot read manifest {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ManifestError(f"Manifest {path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ManifestError(f"Manifest {path} must be a JSON object")
    version = data.get("schema_version")
    if version != MANIFEST_SCHEMA_VERSION:
        raise ManifestError(
            f"Manifest schema version {version!r} is not supported "
            f"(expected {MANIFEST_SCHEMA_VERSION})"
        )
    return ChaffManifest.from_dict(data)


def manifest_for_run(run_root: Path) -> ChaffManifest:
    """Load the manifest of a run directory."""
    return read_manifest(run_root / MANIFEST_FILENAME)


def read_journal(path: Path) -> list[dict[str, Any]]:
    """Read a JSONL journal, tolerating a truncated final line."""
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    with path.open("rb") as handle:
        for raw_line in handle:
            stripped = raw_line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                break  # truncated tail from a crash: keep what came before
            if isinstance(record, dict):
                records.append(record)
    return records


def journal_files(path: Path) -> list[FileRecord]:
    """File records recorded in a journal, in write order."""
    records: list[FileRecord] = []
    for entry in read_journal(path):
        if entry.get("event") == "file":
            try:
                records.append(FileRecord.from_dict(entry))
            except (KeyError, TypeError, ValueError):
                continue  # malformed record: skip, keep verifying the rest
    return records


@dataclass(frozen=True)
class RunInfo:
    """A discovered run directory and its identity."""

    root: Path
    run_id: str
    created_at: str
    app_version: str
    has_manifest: bool
    file_count: int
    bytes_written: int
    status: str


def discover_runs(root: Path) -> list[RunInfo]:
    """Find chaff run directories under ``root`` (non-recursive).

    A directory qualifies when it contains a parsable ``.chaff-run.json``
    marker. Directories that merely look like runs are ignored — the marker
    is the identity, and cleanup relies on that.
    """
    if not root.is_dir():
        return []
    runs: list[RunInfo] = []
    for entry in sorted(root.iterdir()):
        if not entry.is_dir() or entry.is_symlink():
            continue
        marker_path = entry / RUN_MARKER_FILENAME
        if not marker_path.is_file():
            continue
        marker = _read_marker(marker_path)
        if marker is None:
            continue
        manifest_path = entry / MANIFEST_FILENAME
        manifest: ChaffManifest | None = None
        if manifest_path.is_file():
            try:
                manifest = read_manifest(manifest_path)
            except ManifestError:
                manifest = None
        runs.append(
            RunInfo(
                root=entry,
                run_id=str(marker.get("run_id", entry.name)),
                created_at=str(marker.get("created_at", "")),
                app_version=str(marker.get("app_version", "")),
                has_manifest=manifest is not None,
                file_count=manifest.file_count if manifest else 0,
                bytes_written=manifest.bytes_written if manifest else 0,
                status=manifest.status if manifest else "incomplete",
            )
        )
    runs.sort(key=lambda info: info.created_at, reverse=True)
    return runs


def _read_marker(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) and data.get("chaff_run") is True else None


def parse_run_timestamp(created_at: str) -> datetime | None:
    """Best-effort parse of a run's creation timestamp."""
    try:
        return datetime.fromisoformat(created_at)
    except ValueError:
        return None
