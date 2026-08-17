"""Local run history (spec section 49).

A lightweight JSON list in the platform data directory. It is a convenience
index only — the authoritative record of every run is its manifest.
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC
from pathlib import Path

from chaff_generator.core.models import GenerationResult
from chaff_generator.version import __version__

#: History entries kept; the manifest remains the real record.
MAX_HISTORY_ENTRIES = 200


@dataclass
class HistoryEntry:
    """One remembered run (§49: uuid, path, date, size, files, status…)."""

    run_id: str
    path: str
    date: str
    size_bytes: int
    file_count: int
    profile: str
    status: str
    last_verification: str = ""
    app_version: str = field(default=__version__)


class RunHistory:
    """Thread-safe JSON-file-backed history of recent runs."""

    def __init__(self, path: Path | None = None) -> None:
        if path is None:
            from platformdirs import user_data_dir

            path = Path(user_data_dir("chaff-generator")) / "runs-history.json"
        self._path = path
        self._lock = threading.Lock()
        self._entries: list[HistoryEntry] = list(self._load())

    # -- queries ------------------------------------------------------------

    def entries(self) -> list[HistoryEntry]:
        with self._lock:
            return list(self._entries)

    def find_by_path(self, path: Path) -> HistoryEntry | None:
        wanted = str(path)
        with self._lock:
            for entry in self._entries:
                if entry.path == wanted:
                    return entry
        return None

    # -- updates --------------------------------------------------------------

    def record_generation(self, result: GenerationResult) -> HistoryEntry | None:
        """Add/refresh an entry from a finished run; returns it (or None
        when the run never got a root)."""
        if not result.run_root.name:
            return None
        entry = HistoryEntry(
            run_id=result.run_id,
            path=str(result.run_root),
            date=_now_iso(),
            size_bytes=result.bytes_written,
            file_count=result.files_created,
            profile="",  # filled by the caller from the config if known
            status=result.status.value,
        )
        self._upsert(entry)
        return entry

    def record_verification(self, run_root: Path, summary: str) -> None:
        """Stamp the last-verification summary onto a run's entry.

        A run first verified without having been generated through this
        application still earns an entry (§49: history of generated *or
        verified* runs), sourced from its manifest — the authority.
        """
        with self._lock:
            for existing in self._entries:
                if existing.path == str(run_root):
                    existing.last_verification = summary
                    self._save()
                    return
        fresh = self._entry_from_manifest(run_root)
        if fresh is not None:
            fresh.last_verification = summary
            self._upsert(fresh)

    def _entry_from_manifest(self, run_root: Path) -> HistoryEntry | None:
        from chaff_generator.manifest.models import MANIFEST_FILENAME
        from chaff_generator.manifest.reader import read_manifest

        try:
            manifest = read_manifest(run_root / MANIFEST_FILENAME)
        except Exception:
            return None
        return HistoryEntry(
            run_id=manifest.run_id,
            path=str(run_root),
            date=manifest.created_at,
            size_bytes=manifest.bytes_written,
            file_count=manifest.file_count,
            profile=manifest.profile,
            status=manifest.status,
        )

    def set_profile(self, run_root: Path, profile: str) -> None:
        with self._lock:
            for entry in self._entries:
                if entry.path == str(run_root):
                    entry.profile = profile
                    break
        self._save()

    def remove(self, path: Path) -> None:
        with self._lock:
            self._entries = [e for e in self._entries if e.path != str(path)]
        self._save()

    # -- persistence --------------------------------------------------------

    def _upsert(self, entry: HistoryEntry) -> None:
        with self._lock:
            self._entries = [e for e in self._entries if e.path != entry.path]
            self._entries.insert(0, entry)
            del self._entries[MAX_HISTORY_ENTRIES:]
        self._save()

    def _load(self) -> list[HistoryEntry]:
        if not self._path.is_file():
            return []
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        entries = []
        for item in raw if isinstance(raw, list) else []:
            try:
                entries.append(HistoryEntry(**item))
            except TypeError:
                continue  # tolerate entries from other versions
        return entries

    def _save(self) -> None:
        with self._lock:
            payload = [asdict(entry) for entry in self._entries]
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError:
            # History is a convenience; never crash the UI over it.
            pass


def _now_iso() -> str:
    from datetime import datetime

    return datetime.now(UTC).isoformat(timespec="seconds")
