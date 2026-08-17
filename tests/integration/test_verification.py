"""VerificationEngine tests — including the spec section 75 critical test.

Every run here is 1-20 MiB inside pytest ``tmp_path`` (section 72).
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from chaff_generator import ChaffEngine
from chaff_generator.core.models import FileTypeSetting, RunStatus, TargetMode, TargetSpec, Verdict
from chaff_generator.manifest.reader import manifest_for_run
from chaff_generator.manifest.verifier import (
    VerificationEngine,
    VerificationMode,
    verify_run,
)

FORMATS = ("txt", "log", "md", "html", "csv", "json", "xml")


def _generate(tmp_path: Path, amount: int, seed: int = 481_925, min_files: int = 4):
    """Generate a multi-file run with the profile's own format weights.

    Small volumes occasionally collapse into 2 files (one big draw eats the
    remainder via the exact-tail finalizer — legal planner behavior). The
    tamper tests need several files, so walk a fixed seed list until the run
    has enough; the walk itself is deterministic, so every OS picks the same
    seed.
    """
    from chaff_generator.content.bank import load_default_pack
    from chaff_generator.profiles.loader import resolve_profile
    from conftest import make_config

    tmp_path.mkdir(parents=True, exist_ok=True)
    weights = resolve_profile("realistic-desktop", load_default_pack().profiles()).format_weights

    result = None
    for attempt in range(8):
        config = replace(
            make_config(tmp_path),
            target=TargetSpec(path=tmp_path, mode=TargetMode.EXACT, amount=amount),
            seed=seed + attempt,
            profile="realistic-desktop",
            file_types={
                fmt: FileTypeSetting(enabled=True, weight=weights.get(fmt, 1)) for fmt in FORMATS
            },
        )
        candidate = ChaffEngine(config).generate()
        assert candidate.status is RunStatus.COMPLETED
        if len(manifest_for_run(candidate.run_root).files) >= min_files:
            result = candidate
            break
    assert result is not None, "no seed in the fixed walk produced a multi-file run"
    return result


class TestFullVerification:
    def test_fresh_run_is_all_intact(self, tmp_path: Path):
        result = _generate(tmp_path, 1 << 20)
        report = verify_run(result.run_root)
        assert report.ok
        assert report.counts[Verdict.INTACT] == report.files_total
        assert report.bytes_verified == result.bytes_written

    def test_manifest_path_argument_accepted(self, tmp_path: Path):
        result = _generate(tmp_path, 1 << 20)
        report = verify_run(result.run_root / ".chaff-manifest.json")
        assert report.ok

    def test_missing_manifest_raises(self, tmp_path: Path):
        from chaff_generator.core.errors import VerificationError

        (tmp_path / ".chaff-run.json").write_text("{}", encoding="utf-8")
        with pytest.raises(VerificationError):
            verify_run(tmp_path)

    def test_empty_manifest_raises(self, tmp_path: Path):
        from chaff_generator.core.errors import VerificationError
        from chaff_generator.manifest.models import RunMarker
        from chaff_generator.manifest.writer import new_manifest, write_manifest, write_run_marker

        write_run_marker(
            tmp_path, RunMarker(run_id="r", created_at="2026-08-16T00:00:00", app_version="0.1.0")
        )
        manifest = new_manifest(
            run_id="r",
            created_at="2026-08-16T00:00:00",
            app_version="0.1.0",
            target_bytes=0,
            profile="p",
            pack_id="d",
            pack_version="1",
            seed=1,
        )
        write_manifest(tmp_path, manifest)
        with pytest.raises(VerificationError):
            verify_run(tmp_path)


class TestSection75Critical:
    """The spec's canonical tamper scenario (cleanup half lands in Phase 6)."""

    def test_tamper_and_delete_are_caught(self, tmp_path: Path):
        result = _generate(tmp_path, 4 << 20)
        run_root = result.run_root
        assert verify_run(run_root).ok, "fresh run must verify INTACT"

        manifest = manifest_for_run(run_root)
        assert len(manifest.files) >= 3
        tamper_target = run_root / manifest.files[0].relative_path
        delete_target = run_root / manifest.files[1].relative_path

        # Tamper: flip bytes without changing the size -> HASH_MISMATCH.
        payload = bytearray(tamper_target.read_bytes())
        payload[0] ^= 0xFF
        payload[len(payload) // 2] ^= 0xFF
        tamper_target.write_bytes(bytes(payload))
        assert tamper_target.stat().st_size == manifest.files[0].size

        # Delete: a whole file vanishes -> MISSING.
        delete_target.unlink()

        report = verify_run(run_root)
        assert not report.ok
        counts = report.counts
        assert counts[Verdict.HASH_MISMATCH] == 1
        assert counts[Verdict.MISSING] == 1
        assert counts[Verdict.INTACT] == len(manifest.files) - 2
        affected = {r.relative_path: r.verdict for r in report.affected}
        assert affected[manifest.files[0].relative_path] is Verdict.HASH_MISMATCH
        assert affected[manifest.files[1].relative_path] is Verdict.MISSING

    def test_size_change_is_caught_before_hashing(self, tmp_path: Path):
        result = _generate(tmp_path, 1 << 20)
        manifest = manifest_for_run(result.run_root)
        target = result.run_root / manifest.files[0].relative_path
        with target.open("ab") as handle:  # append -> size drifts
            handle.write(b"trailing junk")
        report = verify_run(result.run_root)
        assert report.counts[Verdict.SIZE_MISMATCH] == 1
        first = report.results[0]
        assert first.actual_size == first.expected_size + len(b"trailing junk")


class TestModes:
    def test_metadata_mode_ignores_hash_changes(self, tmp_path: Path):
        """Same-size corruption: metadata mode says INTACT, full mode objects."""
        result = _generate(tmp_path, 1 << 20)
        manifest = manifest_for_run(result.run_root)
        target = result.run_root / manifest.files[0].relative_path
        payload = bytearray(target.read_bytes())
        payload[-1] ^= 0x01
        target.write_bytes(bytes(payload))

        metadata_report = verify_run(result.run_root, VerificationMode.METADATA)
        assert metadata_report.ok, "metadata mode checks sizes only"

        full_report = verify_run(result.run_root, VerificationMode.FULL)
        assert not full_report.ok
        assert full_report.counts[Verdict.HASH_MISMATCH] == 1

    def test_sample_mode_is_reproducible(self, tmp_path: Path):
        result = _generate(tmp_path, 2 << 20, min_files=6)
        manifest = manifest_for_run(result.run_root)
        engine = VerificationEngine()
        first = engine.verify(
            result.run_root, VerificationMode.SAMPLE, sample_percent=40, sample_seed=7
        )
        second = engine.verify(
            result.run_root, VerificationMode.SAMPLE, sample_percent=40, sample_seed=7
        )
        assert [r.relative_path for r in first.results] == [r.relative_path for r in second.results]
        assert first.files_checked == second.files_checked
        expected = round(len(manifest.files) * 0.4)
        assert abs(first.files_checked - expected) <= 1

    def test_sample_count(self, tmp_path: Path):
        result = _generate(tmp_path, 2 << 20, min_files=5)
        manifest = manifest_for_run(result.run_root)
        report = verify_run(result.run_root, VerificationMode.SAMPLE, sample_count=2)
        assert report.files_checked == 2
        assert report.files_total == len(manifest.files)

    def test_sample_bad_parameters(self, tmp_path: Path):
        from chaff_generator.core.errors import VerificationError

        result = _generate(tmp_path, 1 << 20)
        with pytest.raises(VerificationError):
            verify_run(result.run_root, VerificationMode.SAMPLE, sample_percent=0)
        with pytest.raises(VerificationError):
            verify_run(result.run_root, VerificationMode.SAMPLE, sample_count=-3)

    def test_cancel_check_aborts(self, tmp_path: Path):
        result = _generate(tmp_path, 1 << 20)
        manifest = manifest_for_run(result.run_root)
        if len(manifest.files) < 3:
            pytest.skip("run produced too few files to cancel mid-scan")
        calls = {"n": 0}

        def cancel_after_two() -> bool:
            calls["n"] += 1
            return calls["n"] > 2

        report = verify_run(result.run_root, cancel_check=cancel_after_two)
        assert report.cancelled
        assert not report.ok
        assert report.files_checked < report.files_total


class TestHostileManifests:
    def _run_with_mutated_manifest(self, tmp_path: Path, mutate):  # type: ignore[no-untyped-def]
        result = _generate(tmp_path, 1 << 20)
        manifest = manifest_for_run(result.run_root)
        mutate(manifest)
        from chaff_generator.manifest.writer import write_manifest

        write_manifest(result.run_root, manifest)
        return result.run_root

    def test_path_escape_marked_unreadable(self, tmp_path: Path):
        def mutate(manifest):  # type: ignore[no-untyped-def]
            manifest.files[0] = replace(manifest.files[0], relative_path="../../etc/passwd")

        run_root = self._run_with_mutated_manifest(tmp_path, mutate)
        report = verify_run(run_root)
        first = report.results[0]
        assert first.verdict is Verdict.UNREADABLE
        assert "path rejected" in (first.error or "")

    def test_absolute_path_marked_unreadable(self, tmp_path: Path):
        def mutate(manifest):  # type: ignore[no-untyped-def]
            manifest.files[0] = replace(manifest.files[0], relative_path="/etc/passwd")

        run_root = self._run_with_mutated_manifest(tmp_path, mutate)
        report = verify_run(run_root)
        assert report.results[0].verdict is Verdict.UNREADABLE

    @pytest.mark.posix_only
    def test_permission_denied_is_unreadable(self, tmp_path: Path):
        result = _generate(tmp_path, 1 << 20)
        manifest = manifest_for_run(result.run_root)
        target = result.run_root / manifest.files[0].relative_path
        target.chmod(0o000)
        try:
            report = verify_run(result.run_root)
            assert report.results[0].verdict is Verdict.UNREADABLE
        finally:
            target.chmod(0o644)  # let tmp_path cleanup succeed

    def test_symlink_replacement_is_missing(self, tmp_path: Path):
        result = _generate(tmp_path, 1 << 20)
        manifest = manifest_for_run(result.run_root)
        target = result.run_root / manifest.files[0].relative_path
        outside = tmp_path / "outside-decoy.txt"
        outside.write_text("decoy", encoding="utf-8")
        target.unlink()
        target.symlink_to(outside)
        report = verify_run(result.run_root)
        assert report.results[0].verdict is Verdict.MISSING


class TestReportSerialization:
    def test_json_round_trip(self, tmp_path: Path):
        result = _generate(tmp_path, 1 << 20)
        report = verify_run(result.run_root)
        data = json.loads(report.to_json())
        assert data["ok"] is True
        assert data["files_checked"] == report.files_checked
        assert data["counts"]["INTACT"] == report.files_total
        assert data["mode"] == "full"
        assert len(data["results"]) == report.files_total
        assert data["results"][0]["verdict"] == "INTACT"

    def test_csv_rows(self, tmp_path: Path):
        result = _generate(tmp_path, 1 << 20)
        report = verify_run(result.run_root)
        lines = report.to_csv().strip().splitlines()
        assert lines[0] == "relative_path,verdict,expected_size,actual_size"
        assert len(lines) == report.files_total + 1
        for line in lines[1:]:
            parts = line.split(",")
            assert parts[1] == "INTACT"
            assert parts[2] == parts[3]

    def test_summary_text_lists_problems(self, tmp_path: Path):
        result = _generate(tmp_path, 1 << 20)
        manifest = manifest_for_run(result.run_root)
        target = result.run_root / manifest.files[0].relative_path
        target.unlink()
        report = verify_run(result.run_root)
        text = report.summary_text()
        assert "PROBLEMS FOUND" in text
        assert "MISSING" in text
        assert manifest.files[0].relative_path in text

    def test_bytes_accounting(self, tmp_path: Path):
        result = _generate(tmp_path, 1 << 20)
        manifest = manifest_for_run(result.run_root)
        (result.run_root / manifest.files[0].relative_path).unlink()
        report = verify_run(result.run_root)
        intact_bytes = sum(f.size for f in manifest.files[1:])
        assert report.bytes_verified == intact_bytes
        assert report.bytes_expected == result.bytes_written


class TestCli:
    def test_verify_and_inspect_commands(self, tmp_path: Path):
        from typer.testing import CliRunner

        from chaff_generator.cli.app import app

        result = _generate(tmp_path, 1 << 20)
        runner = CliRunner()
        ok = runner.invoke(app, ["verify", str(result.run_root)])
        assert ok.exit_code == 0
        assert "Verification: OK" in ok.output

        tamper = result.run_root / manifest_for_run(result.run_root).files[0].relative_path
        tamper.unlink()
        bad = runner.invoke(app, ["verify", str(result.run_root)])
        assert bad.exit_code == 1
        assert "MISSING" in bad.output

        meta = runner.invoke(app, ["verify", str(result.run_root), "--mode", "metadata"])
        assert meta.exit_code == 1  # still missing on disk

        info = runner.invoke(app, ["inspect", str(result.run_root)])
        assert info.exit_code == 0
        assert "Seed" in info.output
        assert "realistic-desktop" in info.output

    def test_verify_json_export(self, tmp_path: Path):
        from typer.testing import CliRunner

        from chaff_generator.cli.app import app

        result = _generate(tmp_path, 1 << 20)
        out = tmp_path / "report.json"
        runner = CliRunner()
        outcome = runner.invoke(app, ["verify", str(result.run_root), "--json", str(out)])
        assert outcome.exit_code == 0
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["ok"] is True
