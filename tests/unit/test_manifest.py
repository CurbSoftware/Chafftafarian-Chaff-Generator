"""Manifest + journal tests: atomicity, truncated tails, run discovery."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chaff_generator.manifest.models import (
    FileRecord,
    RunMarker,
)
from chaff_generator.manifest.reader import (
    discover_runs,
    manifest_for_run,
    read_journal,
)
from chaff_generator.manifest.writer import (
    JournalWriter,
    new_manifest,
    write_manifest,
    write_run_marker,
)


def _record(path: str, size: int = 128) -> FileRecord:
    return FileRecord(
        relative_path=path,
        size=size,
        sha256="0" * 64,
        renderer="txt",
        template_id=None,
        seed=12345,
    )


class TestManifestRoundTrip:
    def test_write_and_read(self, tmp_path: Path):
        manifest = new_manifest(
            run_id="Chaff_Run_20260816_120000_abcd",
            created_at="2026-08-16T12:00:00",
            app_version="0.1.0",
            target_bytes=1_000,
            profile="realistic-desktop",
            pack_id="default",
            pack_version="1.0.0",
            seed=481_925,
        )
        manifest.files.append(_record("Documents/Report.txt"))
        path = write_manifest(tmp_path, manifest)
        assert path.exists()
        loaded = manifest_for_run(tmp_path)
        assert loaded.run_id == manifest.run_id
        assert loaded.files[0].relative_path == "Documents/Report.txt"
        assert loaded.files[0].seed == 12345
        assert loaded.target_bytes == 1_000
        assert loaded.schema_version == 1

    def test_no_temp_file_left_behind(self, tmp_path: Path):
        manifest = new_manifest(
            run_id="r",
            created_at="2026-08-16T12:00:00",
            app_version="0.1.0",
            target_bytes=1,
            profile="p",
            pack_id="d",
            pack_version="1",
            seed=1,
        )
        write_manifest(tmp_path, manifest)
        leftovers = [p for p in tmp_path.iterdir() if "tmp" in p.name or "partial" in p.name]
        assert leftovers == []

    def test_bad_schema_version_rejected(self, tmp_path: Path):
        data = {
            "schema_version": 999,
            "run_id": "r",
            "created_at": "2026-08-16T12:00:00",
            "generator": "chaff-generator",
            "app_version": "0.1.0",
            "status": "completed",
            "target_bytes": 1,
            "bytes_written": 1,
            "files": [],
            "profile": "p",
            "pack_id": "d",
            "pack_version": "1",
            "seed": 1,
        }
        (tmp_path / ".chaff-manifest.json").write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(Exception):  # noqa: B017 — reader raises ManifestError
            manifest_for_run(tmp_path)


class TestJournal:
    def test_append_and_read_back(self, tmp_path: Path):
        journal = JournalWriter(tmp_path)
        journal.append_file(_record("a.txt"))
        journal.append_event("note", info="hello")
        journal.append_file(_record("b.txt"))
        journal.close()
        records = read_journal(tmp_path / ".chaff-journal.jsonl")
        files = [FileRecord.from_dict(r) for r in records if r.get("event") == "file"]
        events = [r for r in records if r.get("event") != "file"]
        assert [f.relative_path for f in files] == ["a.txt", "b.txt"]
        assert events and events[0]["info"] == "hello"

    def test_truncated_final_line_tolerated(self, tmp_path: Path):
        journal = JournalWriter(tmp_path)
        journal.append_file(_record("a.txt"))
        journal.append_file(_record("b.txt"))
        journal.close()
        path = tmp_path / ".chaff-journal.jsonl"
        good = path.read_text(encoding="utf-8")
        path.write_text(good[:-10] + '{"relative_path": "trun', encoding="utf-8")
        records = read_journal(path)
        files = [r for r in records if r.get("event") == "file"]
        assert len(files) == 1


class TestRunMarkerAndDiscovery:
    def _make_run(self, parent: Path, name: str, created: str, status: str = "completed") -> Path:
        run_root = parent / name
        run_root.mkdir()
        write_run_marker(run_root, RunMarker(run_id=name, created_at=created, app_version="0.1.0"))
        manifest = new_manifest(
            run_id=name,
            created_at=created,
            app_version="0.1.0",
            target_bytes=10,
            profile="p",
            pack_id="d",
            pack_version="1",
            seed=1,
        )
        manifest.status = status
        manifest.files.append(_record("x.txt"))
        write_manifest(run_root, manifest)
        return run_root

    def test_discover_runs_newest_first(self, tmp_path: Path):
        self._make_run(tmp_path, "Chaff_Run_20260816_110000_aaaa", "2026-08-16T11:00:00")
        self._make_run(tmp_path, "Chaff_Run_20260816_120000_bbbb", "2026-08-16T12:00:00")
        self._make_run(tmp_path, "Chaff_Run_20260815_090000_cccc", "2026-08-15T09:00:00")
        runs = discover_runs(tmp_path)
        assert [r.run_id for r in runs] == [
            "Chaff_Run_20260816_120000_bbbb",
            "Chaff_Run_20260816_110000_aaaa",
            "Chaff_Run_20260815_090000_cccc",
        ]
        assert runs[0].file_count == 1
        assert runs[0].status == "completed"

    def test_discover_ignores_non_runs(self, tmp_path: Path):
        self._make_run(tmp_path, "Chaff_Run_20260816_110000_aaaa", "2026-08-16T11:00:00")
        (tmp_path / "user_files").mkdir()
        (tmp_path / "notes.txt").write_text("hello", encoding="utf-8")
        bogus = tmp_path / "fake-run"
        bogus.mkdir()
        (bogus / ".chaff-run.json").write_text('{"chaff_run": false}', encoding="utf-8")
        runs = discover_runs(tmp_path)
        assert [r.run_id for r in runs] == ["Chaff_Run_20260816_110000_aaaa"]

    def test_marker_identifies_chaff_run(self, tmp_path: Path):
        run_root = self._make_run(tmp_path, "Chaff_Run_20260816_110000_aaaa", "2026-08-16T11:00:00")
        data = json.loads((run_root / ".chaff-run.json").read_text(encoding="utf-8"))
        assert data["chaff_run"] is True
        assert data["app_version"]
