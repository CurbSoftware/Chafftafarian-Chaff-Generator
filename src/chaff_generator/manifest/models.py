"""Manifest data models (spec section 34).

A run's manifest is the authoritative record of what was generated: every
file's relative path, size, and SHA-256, plus the run's configuration
fingerprint. Paths are stored POSIX-style relative to the run root so a
manifest stays valid when a run directory is moved between operating systems.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

MANIFEST_SCHEMA_VERSION = 1
MANIFEST_FILENAME = ".chaff-manifest.json"
JOURNAL_FILENAME = ".chaff-journal.jsonl"
RUN_MARKER_FILENAME = ".chaff-run.json"


@dataclass(frozen=True)
class FileRecord:
    """One generated file as recorded at generation time."""

    relative_path: str
    size: int
    sha256: str
    renderer: str
    template_id: str | None
    seed: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "relative_path": self.relative_path,
            "size": self.size,
            "sha256": self.sha256,
            "renderer": self.renderer,
            "template_id": self.template_id,
            "seed": self.seed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FileRecord:
        return cls(
            relative_path=str(data["relative_path"]),
            size=int(data["size"]),
            sha256=str(data["sha256"]),
            renderer=str(data.get("renderer", "")),
            template_id=data.get("template_id"),
            seed=int(data.get("seed", 0)),
        )


@dataclass
class ChaffManifest:
    """The full record of one generation run."""

    schema_version: int
    run_id: str
    created_at: str
    generator: str
    app_version: str
    status: str
    target_bytes: int
    bytes_written: int
    files: list[FileRecord] = field(default_factory=list)
    profile: str = ""
    pack_id: str = ""
    pack_version: str = ""
    seed: int = 0
    free_bytes_after: int | None = None

    @property
    def file_count(self) -> int:
        return len(self.files)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "created_at": self.created_at,
            "generator": self.generator,
            "app_version": self.app_version,
            "status": self.status,
            "target_bytes": self.target_bytes,
            "bytes_written": self.bytes_written,
            "profile": self.profile,
            "pack": {"id": self.pack_id, "version": self.pack_version},
            "seed": self.seed,
            "free_bytes_after": self.free_bytes_after,
            "files": [record.to_dict() for record in self.files],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChaffManifest:
        pack = data.get("pack") or {}
        return cls(
            schema_version=int(data.get("schema_version", 0)),
            run_id=str(data.get("run_id", "")),
            created_at=str(data.get("created_at", "")),
            generator=str(data.get("generator", "")),
            app_version=str(data.get("app_version", "")),
            status=str(data.get("status", "unknown")),
            target_bytes=int(data.get("target_bytes", 0)),
            bytes_written=int(data.get("bytes_written", 0)),
            files=[FileRecord.from_dict(item) for item in data.get("files", [])],
            profile=str(data.get("profile", "")),
            pack_id=str(pack.get("id", "")),
            pack_version=str(pack.get("version", "")),
            seed=int(data.get("seed", 0)),
            free_bytes_after=data.get("free_bytes_after"),
        )


@dataclass(frozen=True)
class RunMarker:
    """The small identity file that marks a directory as a chaff run."""

    run_id: str
    created_at: str
    app_version: str
    manifest: str = MANIFEST_FILENAME

    def to_dict(self) -> dict[str, Any]:
        return {
            "chaff_run": True,
            "run_id": self.run_id,
            "created_at": self.created_at,
            "app_version": self.app_version,
            "manifest": self.manifest,
        }
