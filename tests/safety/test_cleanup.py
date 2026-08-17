"""Phase 6 safety suite: cleanup validates before it destroys (spec §38-41).

Every destructive test runs inside ``tmp_path``. Neighbors — sibling files,
sibling directories, nested unrelated content — must always survive.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from chaff_generator import ChaffEngine
from chaff_generator.cleanup import (
    CleanupManager,
    CleanupSafetyError,
    explain_trash_failure,
    validate_run_root,
)
from chaff_generator.core.models import CompletionAction, TargetMode, TargetSpec
from chaff_generator.manifest.models import MANIFEST_FILENAME, RUN_MARKER_FILENAME
from conftest import make_config


def _generate_run(target: Path, *, amount: int = 120_000, seed: int = 11) -> Path:
    """A tiny real run inside ``target`` (a few hundred KiB, spec §72)."""
    config = replace(
        make_config(target),
        target=TargetSpec(path=target, mode=TargetMode.EXACT, amount=amount),
        seed=seed,
    )
    result = ChaffEngine(config).generate()
    assert result.status.value == "completed"
    return result.run_root


@pytest.fixture()
def populated_target(tmp_path: Path) -> tuple[Path, Path]:
    """A target holding one chaff run plus unrelated neighbors."""
    target = tmp_path / "runs"
    target.mkdir()
    (target / "user.txt").write_text("not chaff", encoding="utf-8")
    neighbor_dir = target / "vacation-photos"
    neighbor_dir.mkdir()
    (neighbor_dir / "img.png").write_bytes(b"\x89PNG not really")
    run_root = _generate_run(target)
    return target, run_root


class TestValidateRunRoot:
    def test_accepts_genuine_run(self, populated_target: tuple[Path, Path]):
        validate_run_root(populated_target[1])  # must not raise

    def test_refuses_missing_directory(self, tmp_path: Path):
        with pytest.raises(CleanupSafetyError, match="does not exist"):
            validate_run_root(tmp_path / "Chaff_Run_20990101_000000_dead")

    def test_refuses_wrong_basename(self, populated_target: tuple[Path, Path]):
        target, run_root = populated_target
        renamed = target / "my_important_folder"
        shutil.move(str(run_root), str(renamed))
        with pytest.raises(CleanupSafetyError, match="not a chaff run id"):
            validate_run_root(renamed)
        assert renamed.exists()  # nothing was destroyed

    def test_refuses_missing_marker(self, populated_target: tuple[Path, Path]):
        run_root = populated_target[1]
        (run_root / RUN_MARKER_FILENAME).unlink()
        with pytest.raises(CleanupSafetyError, match="missing run marker"):
            validate_run_root(run_root)

    def test_refuses_corrupt_marker(self, populated_target: tuple[Path, Path]):
        run_root = populated_target[1]
        (run_root / RUN_MARKER_FILENAME).write_text("{not json", encoding="utf-8")
        with pytest.raises(CleanupSafetyError, match="unreadable/corrupt"):
            validate_run_root(run_root)

    def test_refuses_marker_without_identity_flag(self, populated_target: tuple[Path, Path]):
        run_root = populated_target[1]
        marker = json.loads((run_root / RUN_MARKER_FILENAME).read_text(encoding="utf-8"))
        del marker["chaff_run"]
        (run_root / RUN_MARKER_FILENAME).write_text(json.dumps(marker), encoding="utf-8")
        with pytest.raises(CleanupSafetyError, match="identity flag"):
            validate_run_root(run_root)

    def test_refuses_run_id_mismatch(self, populated_target: tuple[Path, Path]):
        """A marker claiming a different run id means the directory is not
        what it claims (e.g. copied from elsewhere)."""
        run_root = populated_target[1]
        marker = json.loads((run_root / RUN_MARKER_FILENAME).read_text(encoding="utf-8"))
        marker["run_id"] = "Chaff_Run_20000101_000000_0000"
        (run_root / RUN_MARKER_FILENAME).write_text(json.dumps(marker), encoding="utf-8")
        with pytest.raises(CleanupSafetyError, match="does not match directory"):
            validate_run_root(run_root)

    def test_refuses_missing_manifest(self, populated_target: tuple[Path, Path]):
        run_root = populated_target[1]
        (run_root / MANIFEST_FILENAME).unlink()
        with pytest.raises(CleanupSafetyError, match="missing manifest"):
            validate_run_root(run_root)

    @pytest.mark.parametrize(
        "forbidden_name",
        ["/", "home-root"],
    )
    def test_refuses_forbidden_roots(self, tmp_path: Path, monkeypatch, forbidden_name: str):
        """Real system roots are refused via the FORBIDDEN_ROOTS guard."""
        import chaff_generator.cleanup.safety as safety

        if forbidden_name == "home-root":
            fake_home = tmp_path / "fakehome"
            fake_home.mkdir()
            (fake_home / "Documents").mkdir()
            forbidden = [fake_home, fake_home / "Documents"]
            monkeypatch.setattr(safety, "FORBIDDEN_ROOTS", tuple(forbidden))
            targets = [fake_home, fake_home / "Documents"]
        else:
            monkeypatch.setattr(safety, "FORBIDDEN_ROOTS", (Path("/"),))
            targets = [Path("/")]

        for bad in targets:
            with pytest.raises(CleanupSafetyError, match="protected location"):
                validate_run_root(bad)

    def test_refuses_directory_containing_forbidden_root(self, tmp_path: Path, monkeypatch):
        """Cleaning a parent of a protected location would destroy it too."""
        import chaff_generator.cleanup.safety as safety

        protected = tmp_path / "Documents"
        protected.mkdir()
        outer = protected.parent  # tmp_path contains Documents
        monkeypatch.setattr(safety, "FORBIDDEN_ROOTS", (protected,))
        with pytest.raises(CleanupSafetyError, match="protected location"):
            validate_run_root(outer)

    def test_accepts_run_inside_protected_parent(
        self, populated_target: tuple[Path, Path], monkeypatch
    ):
        """A run that merely *lives* under a protected tree (e.g. a run in
        the home directory) is itself safe to remove: only the run root is
        deleted, never its parent."""
        import chaff_generator.cleanup.safety as safety

        target, run_root = populated_target
        monkeypatch.setattr(safety, "FORBIDDEN_ROOTS", (target,))
        validate_run_root(run_root)  # must not raise

    @pytest.mark.posix_only
    def test_refuses_symlinked_root(self, populated_target: tuple[Path, Path]):
        _, run_root = populated_target
        link = run_root.parent / "Chaff_Run_20990101_000000_beef"
        link.symlink_to(run_root, target_is_directory=True)
        with pytest.raises(CleanupSafetyError, match="symlink"):
            validate_run_root(link)


class TestCleanupManagerDelete:
    def test_delete_removes_run_and_only_the_run(self, populated_target: tuple[Path, Path]):
        target, run_root = populated_target
        result = CleanupManager().clean(run_root, CompletionAction.DELETE)

        assert not run_root.exists()
        assert result.trashed is False
        assert result.mode is CompletionAction.DELETE
        # Neighbors survive: sibling file, sibling directory + content.
        assert (target / "user.txt").read_text(encoding="utf-8") == "not chaff"
        assert (target / "vacation-photos" / "img.png").exists()

    def test_delete_sibling_runs_each_survives_independently(self, tmp_path: Path):
        target = tmp_path / "runs"
        target.mkdir()
        first = _generate_run(target, seed=1)
        second = _generate_run(target, seed=2)

        CleanupManager().clean(first, CompletionAction.DELETE)

        assert not first.exists()
        assert second.exists()
        assert (second / MANIFEST_FILENAME).is_file()

    def test_delete_run_with_unrelated_nested_content(self, tmp_path: Path):
        """Foreign content dropped *inside* the run root goes with the run
        (the root is removed whole, §39) — but only that run's root."""
        target = tmp_path / "runs"
        target.mkdir()
        run_root = _generate_run(target)
        nested = run_root / "notes" / "keep.txt"
        nested.parent.mkdir()
        nested.write_text("user note inside the run", encoding="utf-8")

        CleanupManager().clean(run_root, CompletionAction.DELETE)

        assert not run_root.exists()
        assert not nested.exists()
        assert target.exists()

    def test_keep_is_a_programming_error(self, populated_target: tuple[Path, Path]):
        run_root = populated_target[1]
        with pytest.raises(CleanupSafetyError, match="Nothing to clean"):
            CleanupManager().clean(run_root, CompletionAction.KEEP)
        assert run_root.exists()

    def test_refused_cleanup_leaves_everything(self, populated_target: tuple[Path, Path]):
        target, run_root = populated_target
        (run_root / RUN_MARKER_FILENAME).unlink()
        with pytest.raises(CleanupSafetyError):
            CleanupManager().clean(run_root, CompletionAction.DELETE)
        # The run (minus the marker we removed) and all neighbors remain.
        assert run_root.is_dir()
        assert (target / "user.txt").exists()


class TestCleanupManagerTrash:
    def test_trash_moves_whole_root_in_single_call(
        self, populated_target: tuple[Path, Path], monkeypatch, tmp_path: Path
    ):
        target, run_root = populated_target
        expected_path = str(run_root.resolve(strict=True))
        calls: list[str] = []

        def fake_send2trash(path: str) -> None:
            calls.append(path)
            shutil.move(path, str(tmp_path / "trashbin"))

        import send2trash

        monkeypatch.setattr(send2trash, "send2trash", fake_send2trash)

        result = CleanupManager().clean(run_root, CompletionAction.TRASH)

        assert calls == [expected_path]  # one call, whole root
        assert result.trashed is True
        assert not run_root.exists()
        assert any("trash is emptied" in w.lower() for w in result.warnings)
        assert (target / "user.txt").exists()

    def test_trash_failure_maps_to_safety_error(
        self, populated_target: tuple[Path, Path], monkeypatch
    ):
        _, run_root = populated_target

        def boom(path: str) -> None:
            raise OSError("no GIO")

        import send2trash

        monkeypatch.setattr(send2trash, "send2trash", boom)
        with pytest.raises(CleanupSafetyError, match="trash failed"):
            CleanupManager().clean(run_root, CompletionAction.TRASH)
        assert run_root.exists()  # untouched

    def test_explanation_names_the_platform(self):
        message = explain_trash_failure(OSError("boom"))
        assert "boom" in message
        assert "--mode delete" in message  # always offers the fallback


class TestCompletionActionWiring:
    """§41: destructive automatic actions fire only on successful runs."""

    def _config(self, target: Path, completion: CompletionAction):
        return replace(
            make_config(target),
            target=TargetSpec(path=target, mode=TargetMode.EXACT, amount=60_000),
            completion=completion,
        )

    def test_delete_after_completed_run(self, tmp_path: Path):
        target = tmp_path / "runs"
        target.mkdir()
        result = ChaffEngine(self._config(target, CompletionAction.DELETE)).generate()
        assert result.status.value == "completed"
        cleaned = CleanupManager().execute_completion_action(result, CompletionAction.DELETE)
        assert cleaned is not None and not result.run_root.exists()

    def test_keep_does_nothing(self, tmp_path: Path):
        target = tmp_path / "runs"
        target.mkdir()
        result = ChaffEngine(self._config(target, CompletionAction.KEEP)).generate()
        assert CleanupManager().execute_completion_action(result, CompletionAction.KEEP) is None
        assert result.run_root.exists()

    def test_failed_run_keeps_evidence(self, tmp_path: Path, monkeypatch):
        """A failed run must be kept for debugging even with DELETE set (§41)."""
        target = tmp_path / "runs"
        target.mkdir()
        engine = ChaffEngine(self._config(target, CompletionAction.DELETE))

        def broken_render(self, run_root, planned, monitor):
            raise OSError("disk went away")

        monkeypatch.setattr(ChaffEngine, "_render_file", broken_render)
        result = engine.generate()
        assert result.status.value == "failed"
        assert result.run_root.is_dir()  # a real run root was created...

        assert CleanupManager().execute_completion_action(result, CompletionAction.DELETE) is None
        assert result.run_root.is_dir()  # ...and survives for inspection

    def test_cancelled_run_keeps_evidence(self, tmp_path: Path, monkeypatch):
        """Same rule for cancellation (§41)."""
        target = tmp_path / "runs"
        target.mkdir()
        engine = ChaffEngine(self._config(target, CompletionAction.TRASH))

        original = ChaffEngine._render_file

        def render_once_then_cancel(self, run_root, planned, monitor):
            outcome = original(self, run_root, planned, monitor)
            engine.cancel()
            return outcome

        monkeypatch.setattr(ChaffEngine, "_render_file", render_once_then_cancel)
        result = engine.generate()
        assert result.status.value == "cancelled"
        assert CleanupManager().execute_completion_action(result, CompletionAction.TRASH) is None
        assert result.run_root.is_dir()


class TestSymlinkScan:
    @pytest.mark.posix_only
    def test_symlinks_inside_run_are_reported(self, populated_target: tuple[Path, Path]):
        from chaff_generator.cleanup import scan_for_symlinks

        _, run_root = populated_target
        link = run_root / "run_link.txt"
        link.symlink_to(run_root.parent / "user.txt")
        found = scan_for_symlinks(run_root)
        assert link in found
