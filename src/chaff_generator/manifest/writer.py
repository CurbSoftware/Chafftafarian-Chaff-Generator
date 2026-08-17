"""Manifest and journal writers (spec sections 34, 35).

Durability policy: the journal is append-only JSONL, flushed after every
record and fsynced every 64 records and at close, so a crash mid-run leaves
a readable record of every file already on disk. The manifest is written
once, atomically (write to a temp file, ``os.replace``), at run end.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO

from chaff_generator.core.errors import ManifestError
from chaff_generator.core.filesystem import fsync_file
from chaff_generator.manifest.models import (
    JOURNAL_FILENAME,
    MANIFEST_FILENAME,
    MANIFEST_SCHEMA_VERSION,
    RUN_MARKER_FILENAME,
    ChaffManifest,
    RunMarker,
)

if TYPE_CHECKING:
    from chaff_generator.manifest.models import FileRecord

#: Journal records between fsyncs; every record is still flushed.
FSYNC_EVERY = 64


class JournalWriter:
    """Append-only JSONL journal of files as they land on disk."""

    def __init__(self, run_root: Path) -> None:
        self._path = run_root / JOURNAL_FILENAME
        self._count = 0
        self._handle: BinaryIO | None = None
        try:
            self._handle = self._path.open("ab")
        except OSError as exc:
            raise ManifestError(f"Cannot open journal {self._path}: {exc}") from exc

    @property
    def path(self) -> Path:
        return self._path

    def append_file(self, record: FileRecord) -> None:
        """Record one completed file; flush always, fsync periodically."""
        self._write({"event": "file", **record.to_dict()})

    def append_event(self, event: str, **fields: object) -> None:
        """Record a run-level event (started/completed/cancelled/failed)."""
        self._write({"event": event, **fields})

    def _write(self, payload: dict[str, object]) -> None:
        if self._handle is None:
            raise ManifestError("Journal is closed")
        line = json.dumps(payload, sort_keys=False).encode("utf-8") + b"\n"
        try:
            self._handle.write(line)
            self._handle.flush()
        except OSError as exc:
            raise ManifestError(f"Journal write failed: {exc}") from exc
        self._count += 1
        if self._count % FSYNC_EVERY == 0:
            self._sync()

    def _sync(self) -> None:
        if self._handle is None:
            return
        try:
            self._handle.flush()
            fsync_file(self._handle)
        except OSError as exc:
            raise ManifestError(f"Journal fsync failed: {exc}") from exc

    def close(self) -> None:
        """Flush, fsync, and close the journal."""
        if self._handle is not None:
            self._sync()
            self._handle.close()
            self._handle = None


def write_manifest(run_root: Path, manifest: ChaffManifest) -> Path:
    """Write the manifest atomically; returns its final path."""
    manifest_path = run_root / MANIFEST_FILENAME
    temp_path = run_root / f"{MANIFEST_FILENAME}.tmp"
    try:
        with temp_path.open("wb") as handle:
            payload = json.dumps(manifest.to_dict(), indent=2, sort_keys=False) + "\n"
            handle.write(payload.encode("utf-8"))
            handle.flush()
            fsync_file(handle)
        os.replace(temp_path, manifest_path)
    except OSError as exc:
        raise ManifestError(f"Cannot write manifest {manifest_path}: {exc}") from exc
    return manifest_path


def write_run_marker(run_root: Path, marker: RunMarker) -> Path:
    """Write the small run-identity marker file (atomic)."""
    marker_path = run_root / RUN_MARKER_FILENAME
    temp_path = run_root / f"{RUN_MARKER_FILENAME}.tmp"
    try:
        with temp_path.open("wb") as handle:
            payload = json.dumps(marker.to_dict(), indent=2) + "\n"
            handle.write(payload.encode("utf-8"))
            handle.flush()
            fsync_file(handle)
        os.replace(temp_path, marker_path)
    except OSError as exc:
        raise ManifestError(f"Cannot write run marker {marker_path}: {exc}") from exc
    return marker_path


def new_manifest(
    *,
    run_id: str,
    created_at: str,
    app_version: str,
    target_bytes: int,
    profile: str,
    pack_id: str,
    pack_version: str,
    seed: int,
) -> ChaffManifest:
    """Create the manifest skeleton filled in at run start."""
    return ChaffManifest(
        schema_version=MANIFEST_SCHEMA_VERSION,
        run_id=run_id,
        created_at=created_at,
        generator="chaff-generator",
        app_version=app_version,
        status="running",
        target_bytes=target_bytes,
        bytes_written=0,
        profile=profile,
        pack_id=pack_id,
        pack_version=pack_version,
        seed=seed,
    )
