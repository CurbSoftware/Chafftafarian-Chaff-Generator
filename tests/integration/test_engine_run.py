"""ChaffEngine integration tests — the Phase 2 gate (spec sections 34, 72, 75).

Volume discipline: the big run here is 20 MiB into pytest ``tmp_path``,
inside the spec's 1-50 MiB integration-test window. Nothing touches the
host filesystem.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from chaff_generator import ChaffEngine
from chaff_generator.core.events import FileCompleted, RunStarted
from chaff_generator.core.hashing import hash_file
from chaff_generator.core.models import FileTypeSetting, RunStatus, TargetMode, TargetSpec
from chaff_generator.manifest.models import MANIFEST_FILENAME
from chaff_generator.manifest.reader import manifest_for_run

# Formats available in this build phase (Phase 4 adds the office formats).
TEXT_FORMATS = ("txt", "log", "md", "html", "csv", "json", "xml", "dev")


def _engine(tmp_path: Path, amount: int, seed: int = 481_925, **overrides) -> ChaffEngine:
    """An engine over ``realistic-desktop`` restricted to formats this build
    renders today, keeping the profile's own relative weights."""
    from conftest import make_config

    tmp_path.mkdir(parents=True, exist_ok=True)
    config = make_config(tmp_path)
    profile = overrides.pop("profile", "realistic-desktop")
    if "file_types" not in overrides:
        from chaff_generator.content.bank import load_default_pack
        from chaff_generator.profiles.loader import resolve_profile

        weights = resolve_profile(profile, load_default_pack().profiles()).format_weights
        overrides["file_types"] = {
            fmt: FileTypeSetting(enabled=True, weight=weights.get(fmt, 1)) for fmt in TEXT_FORMATS
        }
    config = replace(
        config,
        target=TargetSpec(path=tmp_path, mode=TargetMode.EXACT, amount=amount),
        seed=seed,
        profile=profile,
        **overrides,
    )
    return ChaffEngine(config)


class TestFullRun:
    def test_twenty_mib_run_matches_manifest(self, tmp_path: Path):
        """The gate: 20 MiB, exact byte accounting, manifest == disk."""
        engine = _engine(tmp_path, amount=20 << 20)
        summary = engine.preflight()
        assert summary.estimated_file_count > 0
        assert summary.requested_bytes == 20 << 20

        result = engine.generate()
        assert result.status is RunStatus.COMPLETED
        assert result.bytes_written == 20 << 20, "exact-mode run must land on the target"
        assert result.files_created >= 5

        manifest = manifest_for_run(result.run_root)
        assert manifest.status == "completed"
        assert manifest.bytes_written == 20 << 20
        assert len(manifest.files) == result.files_created

        total_on_disk = 0
        for record in manifest.files:
            on_disk = result.run_root / record.relative_path
            assert on_disk.is_file(), f"manifest lists {record.relative_path}, missing on disk"
            assert on_disk.stat().st_size == record.size, f"size drift: {record.relative_path}"
            assert hash_file(on_disk) == record.sha256, f"hash drift: {record.relative_path}"
            total_on_disk += record.size
        assert total_on_disk == 20 << 20
        # No partial files left behind.
        leftovers = [p for p in result.run_root.rglob("*") if p.name.endswith(".chaff-partial")]
        assert leftovers == []

    def test_run_root_and_marker(self, tmp_path: Path):
        engine = _engine(tmp_path, amount=1 << 20)
        result = engine.generate()
        assert result.run_root.name.startswith("Chaff_Run_")
        assert result.run_root.parent == tmp_path
        marker = result.run_root / ".chaff-run.json"
        assert marker.is_file()
        manifest_path = result.run_root / MANIFEST_FILENAME
        assert manifest_path.is_file()

    def test_unrelated_files_survive(self, tmp_path: Path):
        """Generation only writes inside its own run root (section 72)."""
        sentinel = tmp_path / "user-notes.txt"
        sentinel.write_text("pre-existing user data", encoding="utf-8")
        engine = _engine(tmp_path, amount=1 << 20)
        result = engine.generate()
        assert result.run_root != tmp_path
        assert sentinel.read_text(encoding="utf-8") == "pre-existing user data"
        assert sentinel not in result.run_root.rglob("*")


class TestDeterminism:
    def test_same_seed_same_plan_and_content(self, tmp_path: Path):
        """Same master seed: identical relative paths, sizes, and bytes."""
        first = _engine(tmp_path / "a", amount=4 << 20).generate()
        second = _engine(tmp_path / "b", amount=4 << 20).generate()
        assert first.status is RunStatus.COMPLETED
        assert second.status is RunStatus.COMPLETED

        manifest_a = manifest_for_run(first.run_root)
        manifest_b = manifest_for_run(second.run_root)
        plan_a = [(f.relative_path, f.size, f.renderer, f.template_id) for f in manifest_a.files]
        plan_b = [(f.relative_path, f.size, f.renderer, f.template_id) for f in manifest_b.files]
        assert plan_a == plan_b, "file plan diverged under the same seed"
        for record in manifest_a.files:
            bytes_a = (first.run_root / record.relative_path).read_bytes()
            bytes_b = (second.run_root / record.relative_path).read_bytes()
            assert bytes_a == bytes_b, f"{record.relative_path} not byte-identical"

    def test_different_seed_different_plan(self, tmp_path: Path):
        first = _engine(tmp_path / "a", amount=2 << 20, seed=111).generate()
        second = _engine(tmp_path / "b", amount=2 << 20, seed=222).generate()
        names_a = [f.relative_path for f in manifest_for_run(first.run_root).files]
        names_b = [f.relative_path for f in manifest_for_run(second.run_root).files]
        assert names_a != names_b


class TestLifecycle:
    def test_cancel_stops_early_but_keeps_evidence(self, tmp_path: Path):
        """Cancel mid-run: CANCELLED status, journal + manifest preserved."""
        engine = _engine(tmp_path, amount=4 << 20)
        original_emit = engine._emit

        # Cancel from the event callback the moment the first file lands.
        def emit_and_cancel(event: object) -> None:
            original_emit(event)
            if isinstance(event, FileCompleted):
                engine.cancel()

        engine._emit = emit_and_cancel  # type: ignore[method-assign]
        result = engine.generate()
        assert result.status is RunStatus.CANCELLED
        assert 0 < result.bytes_written < 4 << 20
        assert result.files_created >= 1
        # Evidence preserved: manifest written, records consistent.
        manifest = manifest_for_run(result.run_root)
        assert manifest.status == "cancelled"
        assert len(manifest.files) == result.files_created

    def test_engine_is_single_use(self, tmp_path: Path):
        engine = _engine(tmp_path, amount=64 << 10)
        engine.generate()
        from chaff_generator.core.errors import ChaffError

        with pytest.raises(ChaffError):
            engine.generate()

    def test_preflight_catches_missing_target(self, tmp_path: Path):
        from chaff_generator.core.errors import ChaffError
        from conftest import make_config

        config = replace(
            make_config(tmp_path),
            target=TargetSpec(path=tmp_path / "does-not-exist", mode=TargetMode.EXACT, amount=1024),
        )
        engine = ChaffEngine(config)
        with pytest.raises(ChaffError):
            engine.preflight()

    def test_events_stream_during_run(self, tmp_path: Path):
        events: list[object] = []
        from conftest import make_config

        config = replace(
            make_config(tmp_path),
            target=TargetSpec(path=tmp_path, mode=TargetMode.EXACT, amount=1 << 20),
            file_types={fmt: FileTypeSetting(enabled=True) for fmt in TEXT_FORMATS},
        )
        engine = ChaffEngine(config, event_callback=events.append)
        engine.generate()
        assert any(isinstance(e, RunStarted) for e in events)
        assert any(isinstance(e, FileCompleted) for e in events)

    def test_pause_resume_completes(self, tmp_path: Path):
        """A pause requested mid-run parks at a file boundary, then finishes."""
        engine = _engine(tmp_path, amount=2 << 20)
        resumed = False

        original_emit = engine._emit

        def emit_pause_once(event: object) -> None:
            nonlocal resumed
            original_emit(event)
            if isinstance(event, FileCompleted) and not resumed:
                resumed = True
                engine.pause()
                engine.resume()  # immediately release: exercises both gates

        engine._emit = emit_pause_once  # type: ignore[method-assign]
        result = engine.generate()
        assert result.status is RunStatus.COMPLETED
        assert result.bytes_written == 2 << 20


class TestSafetyRails:
    def test_no_dangerous_paths_in_plan(self, tmp_path: Path):
        """Every planned path stays inside the run root, no absolute/.. escapes."""
        result = _engine(tmp_path, amount=2 << 20).generate()
        manifest = manifest_for_run(result.run_root)
        for record in manifest.files:
            path = record.relative_path
            assert not path.startswith(("/", "\\"))
            assert "\\" not in path, "manifest paths are POSIX-relative"
            assert ".." not in path.split("/")
            resolved = (result.run_root / path).resolve()
            assert resolved.is_relative_to(result.run_root.resolve())

    def test_pdf_unavailable_is_informational(self, tmp_path: Path, monkeypatch):
        """Formats whose dependency is missing are skipped with a warning,
        not a failure (reportlab is installed now, so simulate its absence
        by pointing the registry at a module that cannot import)."""
        from conftest import make_config

        config = replace(
            make_config(tmp_path),
            target=TargetSpec(path=tmp_path, mode=TargetMode.EXACT, amount=1 << 20),
            file_types={
                "txt": FileTypeSetting(enabled=True),
                "pdf": FileTypeSetting(enabled=True),
            },
        )
        engine = ChaffEngine(config)
        monkeypatch.setitem(
            engine._registry._module_table, "pdf", "chaff_generator.renderers.missing_dep"
        )
        summary = engine.preflight()
        assert "txt" in summary.formats
        result = engine.generate()
        assert result.status is RunStatus.COMPLETED
        assert any("pdf" in w.lower() for w in result.warnings)
        manifest_files = manifest_for_run(result.run_root).files
        extensions = {f.relative_path.rsplit(".", 1)[-1] for f in manifest_files}
        assert extensions == {"txt"}
