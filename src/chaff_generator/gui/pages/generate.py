"""The Generate page (spec sections 43-45)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from chaff_generator.content.bank import ChaffBank, default_pack_path
from chaff_generator.core.errors import ChaffError
from chaff_generator.core.models import (
    CompletionAction,
    FileTypeSetting,
    GenerationConfig,
    GenerationResult,
    LayoutMode,
    PreflightSummary,
    TargetMode,
    TargetSpec,
)
from chaff_generator.core.size import format_size
from chaff_generator.gui.widgets import AmountField, FreeSpaceLabel, ProgressPanel, ResultCard
from chaff_generator.gui.workers import CleanupWorker, GenerationWorker
from chaff_generator.renderers import build_registry

_VOLUME_MODES = ("Exact size", "Percent of free space", "Fill until reserve")


class PreflightDialog(QDialog):
    """The §44 preflight summary shown before any data is written."""

    def __init__(self, summary: PreflightSummary, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preflight summary")
        self.setMinimumWidth(560)
        layout = QVBoxLayout(self)

        rows: list[tuple[str, str]] = [
            ("Destination", str(summary.target_path)),
            ("Initial free space", format_size(summary.free_bytes)),
        ]
        if summary.requested_bytes is not None:
            rows.append(("Requested generation", format_size(summary.requested_bytes)))
        if summary.projected_remaining_bytes is not None:
            rows.append(
                ("Expected remaining free space", format_size(summary.projected_remaining_bytes))
            )
        rows.extend(
            [
                ("Estimated number of files", f"{summary.estimated_file_count:,}"),
                ("Selected formats", ", ".join(summary.formats)),
                ("Profile", summary.profile_id),
                ("Seed", str(summary.seed)),
                ("Completion action", summary.completion.value),
                ("Manifest enabled", "yes" if summary.manifest_enabled else "no"),
            ]
        )
        form = QFormLayout()
        for label, value in rows:
            form.addRow(QLabel(label), QLabel(value))
        layout.addLayout(form)

        danger = False
        if summary.projected_remaining_bytes is not None:
            danger = summary.projected_remaining_bytes < 512 << 20  # < 512 MiB left
        if danger:
            warning = QLabel(
                "WARNING: this job may leave dangerously little free space "
                "on the target filesystem."
            )
            warning.setStyleSheet("color: #b91c1c; font-weight: bold;")
            warning.setWordWrap(True)
            layout.addWidget(warning)
        for note in summary.warnings:
            note_label = QLabel(f"Warning: {note}")
            note_label.setWordWrap(True)
            layout.addWidget(note_label)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        start = QPushButton("Start generation")
        start.setDefault(True)
        if danger:
            start.setText("Start anyway")
        cancel.clicked.connect(self.reject)
        start.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(start)
        layout.addLayout(buttons)


class GeneratePage(QWidget):
    """Destination → amount → profile form, then live progress, then result."""

    #: Emitted with the GenerationResult when a run ends (history + runs page).
    run_finished = Signal(object)
    #: Ask the main window to open the Verify page on this run root.
    verification_requested = Signal(Path)
    #: Emitted after a run was successfully deleted/trashed from the card.
    run_removed = Signal(Path)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bank: ChaffBank = ChaffBank.load(default_pack_path())
        self._worker: GenerationWorker | None = None
        self._cleanup_worker: CleanupWorker | None = None
        self._pending_config: GenerationConfig | None = None

        self._build_form()
        self._build_progress()
        self._build_result()

        self.stack = QStackedWidget()
        self.stack.addWidget(self.form_container)
        self.stack.addWidget(self.progress_panel)
        self.stack.addWidget(self.result_card)
        outer = QVBoxLayout(self)
        outer.addWidget(self.stack)

    # -- form ----------------------------------------------------------------

    def _build_form(self) -> None:
        self.form_container = QWidget()
        layout = QVBoxLayout(self.form_container)

        # Destination (§43)
        destination = QGroupBox("Destination")
        dest_layout = QFormLayout(destination)
        self.target_edit = QPushButton(str(Path.home() / "Chaff"))
        self.target_edit.clicked.connect(self._pick_target)
        self.free_space = FreeSpaceLabel()
        dest_layout.addRow("Target directory", self.target_edit)
        dest_layout.addRow("Filesystem", self.free_space)
        layout.addWidget(destination)

        # Amount (§43 "Requested amount")
        amount = QGroupBox("Amount")
        amount_layout = QFormLayout(amount)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(_VOLUME_MODES)
        self.mode_combo.currentIndexChanged.connect(self._mode_changed)
        self.amount_field = AmountField("20 MiB")
        self.percent_spin = QSpinBox()
        self.percent_spin.setRange(1, 100)
        self.percent_spin.setValue(25)
        self.percent_spin.setSuffix("%")
        self.percent_spin.setVisible(False)
        amount_row = QHBoxLayout()
        amount_row.addWidget(self.amount_field)
        amount_row.addWidget(self.percent_spin)
        amount_row.addStretch(1)
        self.reserve_field = AmountField("2 GB")
        amount_layout.addRow("Mode", self.mode_combo)
        amount_layout.addRow("Amount", amount_row)
        amount_layout.addRow("Reserve (always left free)", self.reserve_field)
        layout.addWidget(amount)

        # Content
        content = QGroupBox("Content")
        content_layout = QFormLayout(content)
        self.profile_combo = QComboBox()
        self.layout_combo = QComboBox()
        self.layout_combo.addItems(("realistic", "simple", "flat"))
        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 2_147_483_647)
        self.seed_spin.setSpecialValueText("random")
        content_layout.addRow("Profile", self.profile_combo)
        content_layout.addRow("Directory layout", self.layout_combo)
        content_layout.addRow("Seed", self.seed_spin)
        layout.addWidget(content)

        # File types: unchecked = profile-driven mix (§43 "File Types")
        types_box = QGroupBox("File types (leave all unchecked to follow the profile)")
        types_grid = QGridLayout(types_box)
        self.type_checkboxes: dict[str, QCheckBox] = {}
        for column, fmt in enumerate(sorted(build_registry().ids())):
            check = QCheckBox(fmt)
            self.type_checkboxes[fmt] = check
            types_grid.addWidget(check, column // 4, column % 4)
        layout.addWidget(types_box)

        # Completion (§41)
        completion = QGroupBox("When generation completes")
        completion_layout = QFormLayout(completion)
        self.completion_combo = QComboBox()
        self.completion_combo.addItems(("keep", "delete", "trash"))
        completion_layout.addRow("Action", self.completion_combo)
        layout.addWidget(completion)

        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self._start)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.start_button)
        layout.addLayout(row)
        layout.addStretch(1)

        self.set_bank(self._bank)
        self._refresh_free_space()

    def _build_progress(self) -> None:
        self.progress_panel = ProgressPanel()

    def _build_result(self) -> None:
        self.result_card = ResultCard()
        self.result_card.verify_requested.connect(self.verification_requested.emit)
        self.result_card.open_requested.connect(self._open_folder)
        self.result_card.delete_requested.connect(
            lambda root: self._clean(root, CompletionAction.DELETE)
        )
        self.result_card.trash_requested.connect(
            lambda root: self._clean(root, CompletionAction.TRASH)
        )

    # -- public API ------------------------------------------------------------

    def set_bank(self, bank: ChaffBank) -> None:
        """Adopt a (newly enabled) pack: refresh profile choices."""
        self._bank = bank
        current = self.profile_combo.currentText()
        self.profile_combo.clear()
        profiles = sorted(bank.profiles())
        self.profile_combo.addItems(profiles)
        if current in profiles:
            self.profile_combo.setCurrentText(current)
        elif profiles:
            self.profile_combo.setCurrentText("realistic-desktop")

    def is_busy(self) -> bool:
        return self._worker is not None

    # -- form internals ----------------------------------------------------------

    def _pick_target(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Choose target directory")
        if chosen:
            self.target_edit.setText(chosen)
            self._refresh_free_space()

    def _refresh_free_space(self) -> None:
        target = Path(self.target_edit.text())
        self.free_space.set_path(target if target.is_dir() else target.parent)

    def _mode_changed(self) -> None:
        exact = self.mode_combo.currentIndex() == 0
        self.amount_field.setVisible(exact)
        self.percent_spin.setVisible(not exact)

    def target_path(self) -> Path:
        return Path(self.target_edit.text())

    def _selected_types(self) -> dict[str, FileTypeSetting]:
        return {
            fmt: FileTypeSetting(enabled=check.isChecked())
            for fmt, check in self.type_checkboxes.items()
            if check.isChecked()
        }

    def build_config(self) -> GenerationConfig | None:
        """Config from the form, or None (with a message box) when invalid."""
        target = self.target_path()
        try:
            target.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._error(f"Cannot create target directory:\n{target}\n{exc}")
            return None

        reserve = self.reserve_field.bytes_value()
        if reserve is None:
            self._error(f"Invalid reserve: {self.reserve_field.validation_message()}")
            return None

        mode_index = self.mode_combo.currentIndex()
        percent: Decimal | None = None
        amount: int | None = None
        if mode_index == 0:
            amount = self.amount_field.bytes_value()
            if amount is None:
                self._error(f"Invalid amount: {self.amount_field.validation_message()}")
                return None
        elif mode_index == 1:
            percent = Decimal(self.percent_spin.value())

        spec = TargetSpec(
            path=target,
            mode=TargetMode.EXACT
            if amount is not None
            else (
                TargetMode.PERCENT_FREE if percent is not None else TargetMode.FILL_UNTIL_RESERVE
            ),
            amount=amount,
            percent=percent,
            reserve=reserve,
        )
        return GenerationConfig(
            schema_version=1,
            target=spec,
            profile=self.profile_combo.currentText() or "realistic-desktop",
            seed=self.seed_spin.value(),
            directory_layout=LayoutMode(self.layout_combo.currentText()),
            file_types=self._selected_types(),
            completion=CompletionAction(self.completion_combo.currentText()),
        )

    # -- run lifecycle --------------------------------------------------------

    def _start(self) -> None:
        if self._worker is not None:
            return
        config = self.build_config()
        if config is None:
            return
        try:
            worker = GenerationWorker(config, bank=self._bank)
            summary = worker.preflight()
        except ChaffError as exc:
            self._error(f"Preflight failed:\n{exc}")
            return

        dialog = PreflightDialog(summary, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        self._pending_config = config
        self._worker = worker
        worker.engine_event.connect(self.progress_panel.on_event)
        worker.engine_event.connect(self._on_event)
        worker.finished_run.connect(self._on_finished)
        worker.failed.connect(self._on_failed)
        self.progress_panel.pause_button.clicked.connect(worker.pause)
        self.progress_panel.resume_button.clicked.connect(worker.resume)
        self.progress_panel.cancel_button.clicked.connect(self._on_cancel_clicked)
        self.progress_panel.begin()
        self.stack.setCurrentWidget(self.progress_panel)
        worker.start()

    def _on_event(self, event: object) -> None:
        from chaff_generator.core.events import RunPaused, RunResumed

        if isinstance(event, RunPaused):
            self.progress_panel.set_paused(True)
        elif isinstance(event, RunResumed):
            self.progress_panel.set_paused(False)

    def _on_cancel_clicked(self) -> None:
        if self._worker is not None:
            self._worker.cancel()

    def _teardown_worker(self, worker: GenerationWorker) -> None:
        worker.engine_event.disconnect(self.progress_panel.on_event)
        worker.engine_event.disconnect(self._on_event)
        worker.finished_run.disconnect(self._on_finished)
        worker.failed.disconnect(self._on_failed)
        self.progress_panel.pause_button.clicked.disconnect(worker.pause)
        self.progress_panel.resume_button.clicked.disconnect(worker.resume)
        self.progress_panel.cancel_button.clicked.disconnect(self._on_cancel_clicked)

    def _on_finished(self, result: GenerationResult) -> None:
        assert self._worker is not None
        self._teardown_worker(self._worker)
        self._worker = None
        self.progress_panel.end()
        self.result_card.set_result(result)
        self.stack.setCurrentWidget(self.result_card)
        self._execute_completion(result)
        self.run_finished.emit(result)

    def _on_failed(self, message: str) -> None:
        if self._worker is not None:
            self._teardown_worker(self._worker)
            self._worker = None
        self.progress_panel.end()
        self.stack.setCurrentWidget(self.form_container)
        self._error(f"Generation failed:\n{message}")

    def _execute_completion(self, result: GenerationResult) -> None:
        """§41: apply the configured action — successful runs only."""
        from chaff_generator.core.models import RunStatus

        if self._pending_config is None:
            return
        action = self._pending_config.completion
        self._pending_config = None
        if action is CompletionAction.KEEP or result.status is not RunStatus.COMPLETED:
            return
        if (
            QMessageBox.question(
                self,
                "Completion action",
                f"Generation succeeded. {action.value.capitalize()} the run now?",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        self._clean(result.run_root, action, confirm=False)

    # -- cleanup from the result card ------------------------------------------

    def _clean(self, run_root: Path, mode: CompletionAction, *, confirm: bool = True) -> None:
        if self._cleanup_worker is not None:
            return
        if confirm:
            verb = "permanently delete" if mode is CompletionAction.DELETE else "move to trash"
            if (
                QMessageBox.question(self, "Clean chaff run", f"{verb.capitalize()} {run_root}?")
                != QMessageBox.StandardButton.Yes
            ):
                return
        worker = CleanupWorker(run_root, mode)
        self._cleanup_worker = worker
        worker.finished_cleanup.connect(lambda _r: self._on_cleaned(run_root))
        worker.failed.connect(self._on_clean_failed)
        worker.start()

    def _on_cleaned(self, run_root: Path) -> None:
        if self._cleanup_worker is not None:
            self._cleanup_worker = None
        self.result_card.notify_removed()
        self.run_removed.emit(run_root)

    def _on_clean_failed(self, message: str) -> None:
        self._cleanup_worker = None
        self._error(f"Cleanup failed (the run is still on disk):\n{message}")

    def _open_folder(self, run_root: Path) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(run_root)))

    def _error(self, message: str) -> None:
        QMessageBox.critical(self, "Chaff Generator", message)
