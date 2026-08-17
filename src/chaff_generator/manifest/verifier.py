"""VerificationEngine: manifest-vs-disk integrity checks (spec sections 35-38).

Verdicts, in precedence order:

* ``MISSING``        — the file is gone (or not a regular file)
* ``UNREADABLE``     — it exists but cannot be read (permissions, or the
  manifest path escapes the run root, which a tampered manifest may attempt)
* ``SIZE_MISMATCH``  — size on disk differs from the manifest record
* ``HASH_MISMATCH``  — size matches but SHA-256 does not
* ``INTACT``         — passed every check the selected mode performs

``metadata`` mode stops after the size check; ``full`` hashes every file;
``sample`` hashes a seeded, reproducible subset.
"""

from __future__ import annotations

import json
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Any

from chaff_generator.core.errors import UnsafePathError, VerificationError
from chaff_generator.core.hashing import hash_file
from chaff_generator.core.models import Verdict
from chaff_generator.core.paths import safe_join
from chaff_generator.manifest.models import ChaffManifest, FileRecord
from chaff_generator.manifest.reader import manifest_for_run

#: Cancellation probe: called between files; truthy return aborts the scan.
CancelCheck = Callable[[], bool]


class VerificationMode(StrEnum):
    """How much work a verification pass performs (spec section 37)."""

    METADATA = "metadata"
    FULL = "full"
    SAMPLE = "sample"


@dataclass(frozen=True)
class FileVerdict:
    """One manifest record's check result."""

    relative_path: str
    verdict: Verdict
    expected_size: int
    actual_size: int | None = None
    expected_sha256: str | None = None
    actual_sha256: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "relative_path": self.relative_path,
            "verdict": self.verdict.value,
            "expected_size": self.expected_size,
            "actual_size": self.actual_size,
        }
        if self.expected_sha256 is not None:
            data["expected_sha256"] = self.expected_sha256
        if self.actual_sha256 is not None:
            data["actual_sha256"] = self.actual_sha256
        if self.error is not None:
            data["error"] = self.error
        return data


@dataclass
class VerificationReport:
    """Complete outcome of one verification pass."""

    run_root: Path
    run_id: str
    mode: VerificationMode
    manifest_status: str
    created_at: str
    files_checked: int = 0
    files_total: int = 0
    bytes_verified: int = 0
    bytes_expected: int = 0
    duration_s: float = 0.0
    cancelled: bool = False
    results: list[FileVerdict] = field(default_factory=list)

    @property
    def counts(self) -> dict[Verdict, int]:
        """Occurrences of each verdict (zero-filled across all verdicts)."""
        found = {verdict: 0 for verdict in Verdict}
        for result in self.results:
            found[result.verdict] += 1
        return found

    @property
    def affected(self) -> list[FileVerdict]:
        """Every non-INTACT result, in manifest order (spec section 36)."""
        return [r for r in self.results if r.verdict is not Verdict.INTACT]

    @property
    def ok(self) -> bool:
        """True when every checked file was INTACT and nothing was cancelled."""
        return not self.cancelled and all(r.verdict is Verdict.INTACT for r in self.results)

    def to_dict(self) -> dict[str, Any]:
        counts = self.counts
        return {
            "run_root": str(self.run_root),
            "run_id": self.run_id,
            "mode": self.mode.value,
            "manifest_status": self.manifest_status,
            "created_at": self.created_at,
            "ok": self.ok,
            "cancelled": self.cancelled,
            "files_checked": self.files_checked,
            "files_total": self.files_total,
            "bytes_verified": self.bytes_verified,
            "bytes_expected": self.bytes_expected,
            "counts": {verdict.value: count for verdict, count in counts.items()},
            "results": [r.to_dict() for r in self.results],
        }

    def to_json(self) -> str:
        """The full report as indented JSON."""
        return json.dumps(self.to_dict(), indent=2)

    def to_csv(self) -> str:
        """One row per checked file: path,verdict,expected_size,actual_size."""
        lines = ["relative_path,verdict,expected_size,actual_size"]
        for result in self.results:
            actual = "" if result.actual_size is None else str(result.actual_size)
            lines.append(
                f"{result.relative_path},{result.verdict.value},{result.expected_size},{actual}"
            )
        return "\n".join(lines) + "\n"

    def summary_text(self) -> str:
        """The human summary (spec section 36)."""
        counts = self.counts
        label = "OK" if self.ok else "PROBLEMS FOUND"
        lines = [
            f"Verification: {label}",
            f"Run         : {self.run_id} ({self.run_root})",
            f"Mode        : {self.mode.value} — checked {self.files_checked}"
            f" of {self.files_total} files",
            f"Bytes       : {self.bytes_verified:,} verified of {self.bytes_expected:,} expected",
        ]
        parts = [
            f"{count} {verdict.value}"
            for verdict, count in counts.items()
            if count or verdict is Verdict.INTACT
        ]
        lines.append("Verdicts    : " + ", ".join(parts))
        if self.cancelled:
            lines.append("Note        : cancelled before completion")
        for result in self.affected[:20]:
            detail = f" — {result.error}" if result.error else ""
            lines.append(f"  {result.verdict.value:<13} {result.relative_path}{detail}")
        hidden = len(self.affected) - 20
        if hidden > 20:
            lines.append(f"  ... and {hidden} more")
        return "\n".join(lines)


def _select_sample(
    records: list[FileRecord], percent: float | None, count: int | None, seed: int
) -> list[FileRecord]:
    """Deterministically choose the sample for SAMPLE mode (§37).

    The seed makes the subset reproducible: the same manifest, percent and
    seed always select the same files, on every OS.
    """
    if percent is None and count is None:
        return records
    if percent is not None and not 0 < percent <= 100:
        raise VerificationError(f"sample percent must be in (0, 100], got {percent}")
    if count is not None and count <= 0:
        raise VerificationError(f"sample count must be positive, got {count}")
    size = len(records)
    if count is not None:
        k = min(count, size)
    else:
        assert percent is not None  # narrowed above
        k = max(1, min(size, round(size * percent / 100)))
    rng = random.Random(seed)
    chosen = rng.sample(range(size), k)
    return [records[i] for i in sorted(chosen)]


class VerificationEngine:
    """Compares a run's manifest against what is actually on disk."""

    def verify(
        self,
        run_root: Path,
        mode: VerificationMode = VerificationMode.FULL,
        *,
        sample_percent: float | None = None,
        sample_count: int | None = None,
        sample_seed: int = 0,
        cancel_check: CancelCheck | None = None,
        progress: Callable[[int, int], None] | None = None,
    ) -> VerificationReport:
        """Verify ``run_root`` (or a manifest path) and return the report.

        Raises :class:`VerificationError` when the run root or manifest is
        unusable — a missing manifest is a report-stopping condition, not a
        per-file verdict (there is nothing to verify against).
        """
        started = time.monotonic()
        run_root, manifest = self._load(run_root)

        records = manifest.files
        if mode is VerificationMode.SAMPLE:
            chosen = _select_sample(records, sample_percent, sample_count, sample_seed)
        else:
            chosen = records

        report = VerificationReport(
            run_root=run_root,
            run_id=manifest.run_id,
            mode=mode,
            manifest_status=manifest.status,
            created_at=manifest.created_at,
            files_total=len(records),
        )

        for position, record in enumerate(chosen):
            if cancel_check is not None and cancel_check():
                report.cancelled = True
                break
            result = self._check_one(run_root, record, mode)
            report.results.append(result)
            report.files_checked = position + 1
            if result.verdict is Verdict.INTACT:
                report.bytes_verified += record.size
            report.bytes_expected += record.size
            if progress is not None:
                progress(position + 1, len(chosen))

        report.duration_s = max(time.monotonic() - started, 0.001)
        return report

    # ---------------------------------------------------------------- internals

    def _load(self, path: Path) -> tuple[Path, ChaffManifest]:
        """Accept a run directory or a direct manifest path (spec section 76)."""
        manifest_root = path.parent if path.is_file() and path.name.endswith(".json") else path
        if not manifest_root.is_dir():
            raise VerificationError(f"Not a directory (or manifest file): {path}")
        try:
            manifest = manifest_for_run(manifest_root)
        except VerificationError:
            raise
        except Exception as exc:
            raise VerificationError(f"Could not read the manifest: {exc}") from exc
        if not manifest.files:
            raise VerificationError("The manifest records no files — nothing to verify")
        return manifest_root, manifest

    def _check_one(self, run_root: Path, record: FileRecord, mode: VerificationMode) -> FileVerdict:
        try:
            target = safe_join(run_root, record.relative_path)
        except UnsafePathError as exc:
            # A manifest path that is itself hostile (absolute, traversal) can
            # never be verified; an in-root path that fails the join means the
            # disk state changed under us (e.g. the file was replaced by a
            # symlink) — the recorded file is simply gone.
            raw = str(record.relative_path)
            if raw.startswith(("/", "\\")) or ".." in PurePosixPath(raw).parts:
                return FileVerdict(
                    relative_path=record.relative_path,
                    verdict=Verdict.UNREADABLE,
                    expected_size=record.size,
                    error=f"path rejected: {exc}",
                )
            return FileVerdict(
                relative_path=record.relative_path,
                verdict=Verdict.MISSING,
                expected_size=record.size,
            )

        if not target.exists() or target.is_symlink() or not target.is_file():
            return FileVerdict(
                relative_path=record.relative_path,
                verdict=Verdict.MISSING,
                expected_size=record.size,
            )

        try:
            actual_size = target.stat().st_size
        except OSError as exc:
            return FileVerdict(
                relative_path=record.relative_path,
                verdict=Verdict.UNREADABLE,
                expected_size=record.size,
                error=str(exc),
            )

        if actual_size != record.size:
            return FileVerdict(
                relative_path=record.relative_path,
                verdict=Verdict.SIZE_MISMATCH,
                expected_size=record.size,
                actual_size=actual_size,
            )

        if mode is VerificationMode.METADATA:
            return FileVerdict(
                relative_path=record.relative_path,
                verdict=Verdict.INTACT,
                expected_size=record.size,
                actual_size=actual_size,
            )

        try:
            actual_hash = hash_file(target)
        except OSError as exc:
            return FileVerdict(
                relative_path=record.relative_path,
                verdict=Verdict.UNREADABLE,
                expected_size=record.size,
                actual_size=actual_size,
                error=str(exc),
            )
        if actual_hash != record.sha256:
            return FileVerdict(
                relative_path=record.relative_path,
                verdict=Verdict.HASH_MISMATCH,
                expected_size=record.size,
                actual_size=actual_size,
                expected_sha256=record.sha256,
                actual_sha256=actual_hash,
            )
        return FileVerdict(
            relative_path=record.relative_path,
            verdict=Verdict.INTACT,
            expected_size=record.size,
            actual_size=actual_size,
            expected_sha256=record.sha256,
            actual_sha256=actual_hash,
        )


def verify_run(
    run_root: Path,
    mode: VerificationMode = VerificationMode.FULL,
    **kwargs: Any,
) -> VerificationReport:
    """Convenience wrapper: one-call verification."""
    return VerificationEngine().verify(run_root, mode, **kwargs)
