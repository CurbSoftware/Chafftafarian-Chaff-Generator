"""The Verify page (spec sections 36-37, 48)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from chaff_generator.core.errors import ChaffError
from chaff_generator.core.size import format_size
from chaff_generator.gui.widgets import ReportTable
from chaff_generator.gui.workers import VerifyWorker
from chaff_generator.manifest.models import ChaffManifest
from chaff_generator.manifest.reader import manifest_for_run
from chaff_generator.manifest.verifier import VerificationMode, VerificationReport


class VerifyPage(QWidget):
    """Inspect run metadata, then verify metadata/sample/full (§48)."""

    #: (run_root, summary) after each verification — stamps the Runs page.
    verification_done = Signal(Path, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._manifest: ChaffManifest | None = None
        self._run_root: Path | None = None
        self._report: VerificationReport | None = None
        self._worker: VerifyWorker | None = None

        # -- source selection + metadata inspection --------------------------
        source = QGroupBox("Chaff run")
        source_form = QFormLayout(source)
        self.path_label = QLabel("—")
        self.path_label.setWordWrap(True)
        pick = QPushButton("Select run directory or manifest…")
        pick.clicked.connect(self._pick_run)
        source_form.addRow(pick)
        source_form.addRow("Selected", self.path_label)

        self.meta = QLabel("Metadata: —")
        self.meta.setWordWrap(True)
        source_form.addRow(self.meta)

        # -- verification choices (§48) ---------------------------------------
        choices = QGroupBox("Verification")
        choices_form = QFormLayout(choices)
        self.radio_metadata = QRadioButton("Metadata (existence + size only)")
        self.radio_sample = QRadioButton("Sample")
        self.radio_full = QRadioButton("Full (hash every file)")
        self.radio_full.setChecked(True)
        group = QButtonGroup(self)
        for radio in (self.radio_metadata, self.radio_sample, self.radio_full):
            group.addButton(radio)
        self.sample_combo = QComboBox()
        self.sample_combo.addItems(("10%", "25%", "50%", "count"))
        self.sample_count = QSpinBox()
        self.sample_count.setRange(1, 1_000_000)
        self.sample_count.setValue(10)
        sample_row = QHBoxLayout()
        sample_row.addWidget(self.sample_combo)
        sample_row.addWidget(self.sample_count)
        sample_row.addStretch(1)
        choices_form.addRow(self.radio_metadata)
        choices_form.addRow(self.radio_full)
        choices_form.addRow(self.radio_sample)
        choices_form.addRow("Sample selection", sample_row)
        self.radio_sample.toggled.connect(self._sample_toggled)
        self._sample_toggled(False)

        self.verify_button = QPushButton("Verify")
        self.verify_button.setEnabled(False)
        self.verify_button.clicked.connect(self._verify)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel)
        controls = QHBoxLayout()
        controls.addWidget(self.verify_button)
        controls.addWidget(self.cancel_button)
        controls.addStretch(1)
        choices_form.addRow(controls)

        # -- report (§36) --------------------------------------------------------
        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        self.table = ReportTable()
        self.export_json = QPushButton("Export JSON…")
        self.export_csv = QPushButton("Export CSV…")
        self.export_json.clicked.connect(lambda: self._export("json"))
        self.export_csv.clicked.connect(lambda: self._export("csv"))
        for button in (self.export_json, self.export_csv):
            button.setEnabled(False)
        export_row = QHBoxLayout()
        export_row.addWidget(self.export_json)
        export_row.addWidget(self.export_csv)
        export_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addWidget(source)
        layout.addWidget(choices)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.table, 1)
        layout.addLayout(export_row)

    # -- selection -----------------------------------------------------------

    def select_run(self, path: Path) -> bool:
        """Load a run directory or manifest; returns False when unusable."""
        try:
            manifest = manifest_for_run(path)
        except ChaffError as exc:
            self._error(f"Cannot inspect {path}:\n{exc}")
            return False
        self._run_root = path if path.is_dir() else path.parent
        self._manifest = manifest
        self.path_label.setText(str(self._run_root))
        self.meta.setText(
            f"Metadata: run {manifest.run_id} · {manifest.created_at} · "
            f"{len(manifest.files):,} files · "
            f"{format_size(manifest.bytes_written)} · profile "
            f"{manifest.profile or '—'} · generated by chaff-generator "
            f"{manifest.app_version or '—'} · status {manifest.status}"
        )
        self.verify_button.setEnabled(True)
        return True

    def _pick_run(self) -> None:
        chosen, _filter = QFileDialog.getOpenFileName(
            self, "Select chaff-manifest.json", "", "Chaff manifest (*.json)"
        )
        if not chosen:
            return
        self.select_run(Path(chosen).parent)

    # -- verification ----------------------------------------------------------

    def _sample_toggled(self, on: bool) -> None:
        for widget in (self.sample_combo, self.sample_count):
            widget.setEnabled(on)

    def _mode(self) -> tuple[VerificationMode, float | None, int | None]:
        if self.radio_metadata.isChecked():
            return VerificationMode.METADATA, None, None
        if self.radio_full.isChecked():
            return VerificationMode.FULL, None, None
        selection = self.sample_combo.currentText()
        if selection == "count":
            return VerificationMode.SAMPLE, None, self.sample_count.value()
        return VerificationMode.SAMPLE, float(selection.rstrip("%")), None

    def _verify(self) -> None:
        if self._worker is not None or self._run_root is None:
            return
        mode, percent, count = self._mode()
        self._worker = VerifyWorker(
            self._run_root, mode, sample_percent=percent, sample_count=count
        )
        self._worker.finished_report.connect(self._on_report)
        self._worker.failed.connect(self._on_failed)
        self.verify_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self._worker.start()

    def _cancel(self) -> None:
        if self._worker is not None:
            self._worker.cancel()

    def _on_report(self, report: VerificationReport) -> None:
        self._worker = None
        self._report = report
        self.verify_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.summary_label.setText(report.summary_text())
        self.table.load_report(report)
        for button in (self.export_json, self.export_csv):
            button.setEnabled(True)
        if report.run_root.name:
            self.verification_done.emit(report.run_root, "OK" if report.ok else "PROBLEMS FOUND")

    def _on_failed(self, message: str) -> None:
        self._worker = None
        self.verify_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self._error(f"Verification failed:\n{message}")

    # -- export ------------------------------------------------------------------

    def _export(self, kind: str) -> None:
        if self._report is None:
            return
        suffix = f"JSON (*.{kind})" if kind == "json" else "CSV (*.csv)"
        chosen, _filter = QFileDialog.getSaveFileName(
            self, "Save verification report", f"chaff-verification.{kind}", suffix
        )
        if not chosen:
            return
        content = self._report.to_json() if kind == "json" else self._report.to_csv()
        try:
            Path(chosen).write_text(content, encoding="utf-8")
        except OSError as exc:
            self._error(f"Cannot write {chosen}:\n{exc}")

    def _error(self, message: str) -> None:
        QMessageBox.critical(self, "Chaff Generator", message)
