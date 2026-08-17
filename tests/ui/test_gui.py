"""Phase 7 GUI tests (pytest-qt, offscreen platform).

Real generation runs here are tiny (spec section 72: at most a few MiB,
always inside tmp_path).
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QDialog, QLabel, QMessageBox

from chaff_generator import ChaffEngine
from chaff_generator.core.events import FileStarted
from chaff_generator.core.models import (
    CompletionAction,
    GenerationResult,
    PreflightSummary,
    RunStatus,
    TargetMode,
    TargetSpec,
)
from chaff_generator.core.models import (
    CompletionAction as _Completion,
)
from chaff_generator.gui.main_window import MainWindow
from chaff_generator.gui.pages import PreflightDialog
from chaff_generator.gui.state import RunHistory
from chaff_generator.gui.widgets import AmountField
from conftest import make_config


@pytest.fixture()
def window(qtbot, tmp_path: Path) -> MainWindow:
    """An offscreen MainWindow with tmp-scoped run history."""
    win = MainWindow(history=RunHistory(tmp_path / "history.json"))
    qtbot.addWidget(win)
    yield win
    win.close()


def _generate_run(target: Path, amount: int = 150_000) -> Path:
    target.mkdir(parents=True, exist_ok=True)
    config = replace(
        make_config(target),
        target=TargetSpec(path=target, mode=TargetMode.EXACT, amount=amount),
        seed=23,
    )
    result = ChaffEngine(config).generate()
    assert result.status is RunStatus.COMPLETED
    return result.run_root


def _auto_accept_preflight(monkeypatch) -> None:
    monkeypatch.setattr(PreflightDialog, "exec", lambda self: QDialog.DialogCode.Accepted)


class TestAppShell:
    def test_main_window_launches(self, window: MainWindow):
        assert window.windowTitle().startswith("Chaff Generator")
        assert window.stack.count() == 5
        labels = [window.nav.item(i).text() for i in range(window.nav.count())]
        assert labels == ["Generate", "Verify", "Runs", "ChaffBank", "Settings"]

    def test_navigation_switches_pages(self, window: MainWindow):
        window.nav.setCurrentRow(2)
        assert window.stack.currentIndex() == 2
        assert window.stack.currentWidget() is window.runs_page


class TestAmountField:
    def test_parses_sizes(self, qtbot):
        field = AmountField()
        qtbot.addWidget(field)
        field.setText("20 MiB")
        assert field.bytes_value() == 20 * 2**20
        field.setText("1.5 GB")
        assert field.bytes_value() == 1_500_000_000

    def test_rejects_garbage_with_message(self, qtbot):
        field = AmountField()
        qtbot.addWidget(field)
        field.setText("a bunch")
        assert field.bytes_value() is None
        assert field.validation_message()
        field.setText("-5 MiB")
        assert field.bytes_value() is None


class TestGenerateForm:
    def test_invalid_target_blocks_config(self, window: MainWindow, tmp_path: Path, monkeypatch):
        blocker = tmp_path / "not-a-dir"
        blocker.write_text("file in the way", encoding="utf-8")
        window.generate_page.target_edit.setText(str(blocker / "sub"))

        errors: list[str] = []
        monkeypatch.setattr(
            QMessageBox, "critical", staticmethod(lambda *a, **k: errors.append(a[2]))
        )
        assert window.generate_page.build_config() is None
        assert errors  # the user was told why

    def test_exact_config_shape(self, window: MainWindow, tmp_path: Path):
        page = window.generate_page
        page.target_edit.setText(str(tmp_path / "runs"))
        page.amount_field.setText("1 MiB")
        page.reserve_field.setText("10 MiB")
        config = page.build_config()
        assert config is not None
        assert config.target.mode is TargetMode.EXACT
        assert config.target.amount == 2**20
        assert config.target.reserve == 10 * 2**20

    def test_percent_config_shape(self, window: MainWindow, tmp_path: Path):
        page = window.generate_page
        page.target_edit.setText(str(tmp_path / "runs"))
        page.mode_combo.setCurrentIndex(1)
        page.percent_spin.setValue(30)
        config = page.build_config()
        assert config is not None
        assert config.target.mode is TargetMode.PERCENT_FREE

    def test_fill_config_shape(self, window: MainWindow, tmp_path: Path):
        page = window.generate_page
        page.target_edit.setText(str(tmp_path / "runs"))
        page.mode_combo.setCurrentIndex(2)
        config = page.build_config()
        assert config is not None
        assert config.target.mode is TargetMode.FILL_UNTIL_RESERVE

    def test_type_checkboxes_restrict_formats(self, window: MainWindow, tmp_path: Path):
        page = window.generate_page
        page.target_edit.setText(str(tmp_path / "runs"))
        page.amount_field.setText("1 MiB")
        page.type_checkboxes["txt"].setChecked(True)
        page.type_checkboxes["json"].setChecked(True)
        config = page.build_config()
        assert config is not None
        assert set(config.file_types) == {"txt", "json"}


class TestPreflightDialog:
    def test_shows_required_rows_and_danger(self, qtbot, tmp_path: Path):
        summary = PreflightSummary(
            target_path=tmp_path,
            free_bytes=10 * 2**20,
            requested_bytes=9 * 2**20,
            projected_remaining_bytes=1 * 2**20,
            estimated_file_count=42,
            formats=["txt", "csv"],
            profile_id="realistic-desktop",
            seed=7,
            completion=CompletionAction.KEEP,
            manifest_enabled=True,
            warnings=[],
        )
        dialog = PreflightDialog(summary)
        qtbot.addWidget(dialog)
        all_text = " ".join(label.text() for label in dialog.findChildren(QLabel))
        for needed in (
            "Destination",
            "Initial free space",
            "Requested generation",
            "Expected remaining free space",
            "Estimated number of files",
            "Selected formats",
            "Profile",
            "Seed",
            "Completion action",
            "Manifest enabled",
        ):
            assert needed in all_text
        assert "dangerously little" in all_text  # projected remaining < 512 MiB


class TestGenerationFlow:
    def test_full_run_via_gui(self, window: MainWindow, qtbot, tmp_path: Path, monkeypatch):
        page = window.generate_page
        page.target_edit.setText(str(tmp_path / "runs"))
        page.amount_field.setText("300 KiB")
        page.reserve_field.setText("10 MiB")
        _auto_accept_preflight(monkeypatch)
        with qtbot.waitSignal(page.run_finished, timeout=120_000) as blocker:
            page._start()
        result = blocker.args[0]
        assert isinstance(result, GenerationResult)
        assert result.status is RunStatus.COMPLETED
        assert result.run_root.is_dir()
        # The result card replaced the progress view.
        assert page.stack.currentWidget() is page.result_card
        assert page.result_card.run_root() == result.run_root

    def test_cancel_mid_run_keeps_evidence(
        self, window: MainWindow, qtbot, tmp_path: Path, monkeypatch
    ):
        page = window.generate_page
        page.target_edit.setText(str(tmp_path / "runs"))
        page.amount_field.setText("3 MiB")
        page.reserve_field.setText("10 MiB")
        page.type_checkboxes["txt"].setChecked(True)  # many small files
        _auto_accept_preflight(monkeypatch)

        def cancel_on_first_file(event: object) -> None:
            if isinstance(event, FileStarted) and page._worker is not None:
                page._worker.cancel()

        monkeypatch.setattr(page, "_on_event", cancel_on_first_file)
        with qtbot.waitSignal(page.run_finished, timeout=120_000) as blocker:
            page._start()
        result = blocker.args[0]
        assert result.status is RunStatus.CANCELLED
        assert result.run_root.is_dir()  # §41: evidence preserved

    def test_history_and_runs_page_recorded(
        self, window: MainWindow, qtbot, tmp_path: Path, monkeypatch
    ):
        page = window.generate_page
        page.target_edit.setText(str(tmp_path / "runs"))
        page.amount_field.setText("200 KiB")
        page.reserve_field.setText("10 MiB")
        _auto_accept_preflight(monkeypatch)
        with qtbot.waitSignal(page.run_finished, timeout=120_000):
            page._start()
        assert window.history.entries()
        assert window.runs_page.table.rowCount() == 1


class TestVerifyFlow:
    def test_verify_via_gui(self, window: MainWindow, qtbot, tmp_path: Path):
        run_root = _generate_run(tmp_path / "runs")
        assert window.verify_page.select_run(run_root)
        with qtbot.waitSignal(window.verify_page.verification_done, timeout=60_000) as blocker:
            window.verify_page._verify()
        stamped_root, summary = blocker.args
        assert stamped_root == run_root
        assert summary == "OK"
        assert window.verify_page.table.rowCount() > 0
        entry = window.history.find_by_path(run_root)
        assert entry is not None and entry.last_verification == "OK"

    def test_refuses_non_run_directory(self, window: MainWindow, tmp_path: Path, monkeypatch):
        errors: list[str] = []
        monkeypatch.setattr(
            QMessageBox, "critical", staticmethod(lambda *a, **k: errors.append(a[2]))
        )
        assert window.verify_page.select_run(tmp_path) is False
        assert errors


class TestResultCardSafety:
    def test_delete_refuses_tampered_run(
        self, window: MainWindow, qtbot, tmp_path: Path, monkeypatch
    ):
        """The card's delete goes through validation: a tampered run
        (marker removed) must survive the attempt untouched."""
        from chaff_generator.manifest.models import RUN_MARKER_FILENAME

        run_root = _generate_run(tmp_path / "runs")
        (run_root / RUN_MARKER_FILENAME).unlink()

        monkeypatch.setattr(
            QMessageBox,
            "question",
            staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
        )
        failures: list[str] = []
        monkeypatch.setattr(
            QMessageBox, "critical", staticmethod(lambda *a, **k: failures.append(a[2]))
        )
        page = window.generate_page
        page._clean(run_root, _Completion.DELETE)
        qtbot.waitUntil(lambda: page._cleanup_worker is None, timeout=30_000)
        assert run_root.is_dir()  # validation refused: nothing destroyed
        assert failures  # the refusal was explained to the user
