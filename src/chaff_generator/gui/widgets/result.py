"""Post-run result card and verification report table."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal, SignalInstance
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from chaff_generator.core.models import GenerationResult, RunStatus
from chaff_generator.core.size import format_size
from chaff_generator.manifest.verifier import Verdict, VerificationReport


class ResultCard(QWidget):
    """Summary of a finished run with follow-up actions (§43/§36)."""

    verify_requested = Signal(Path)  # payload: run_root
    open_requested = Signal(Path)  # payload: run_root
    delete_requested = Signal(Path)  # payload: run_root
    trash_requested = Signal(Path)  # payload: run_root

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._result: GenerationResult | None = None

        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        self.notes = QLabel("")
        self.notes.setWordWrap(True)
        self.notes.setVisible(False)

        box = QGroupBox("Run result")
        layout = QVBoxLayout(box)
        layout.addWidget(self.summary)
        layout.addWidget(self.notes)

        self.verify_button = QPushButton("Verify Now")
        self.open_button = QPushButton("Open Folder")
        self.delete_button = QPushButton("Delete Chaff")
        self.trash_button = QPushButton("Move to Trash")
        self.verify_button.clicked.connect(self._emit_run_root(self.verify_requested))
        self.open_button.clicked.connect(self._emit_run_root(self.open_requested))
        self.delete_button.clicked.connect(self._emit_run_root(self.delete_requested))
        self.trash_button.clicked.connect(self._emit_run_root(self.trash_requested))
        buttons = QHBoxLayout()
        for button in (
            self.verify_button,
            self.open_button,
            self.delete_button,
            self.trash_button,
        ):
            buttons.addWidget(button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(box)

    def set_result(self, result: GenerationResult) -> None:
        """Show a GenerationResult (destructive buttons only while it exists)."""
        self._result = result
        if result.status is RunStatus.COMPLETED:
            self.summary.setText(
                f"Done: {result.files_created:,} files, "
                f"{format_size(result.bytes_written)} in {result.duration_s:.1f}s."
            )
        else:
            # §41: failed/cancelled runs keep their evidence for inspection.
            self.summary.setText(
                f"Run {result.status.value}: {result.error or 'stopped early'} "
                f"({result.files_created:,} files, "
                f"{format_size(result.bytes_written)} kept for inspection)."
            )
        self.notes.setVisible(bool(result.warnings))
        self.notes.setText("\n".join(f"Warning: {w}" for w in result.warnings))

    def notify_removed(self) -> None:
        """After a successful delete/trash the run no longer exists."""
        self._result = None
        self.summary.setText("Run removed from disk.")
        self.notes.setVisible(False)
        for button in (
            self.verify_button,
            self.open_button,
            self.delete_button,
            self.trash_button,
        ):
            button.setEnabled(False)

    def run_root(self) -> Path | None:
        """The run root, or None when no run happened (empty Path)."""
        if self._result is None or not self._result.run_root.name:
            return None
        return self._result.run_root

    def _emit_run_root(self, signal: SignalInstance) -> object:
        # Returns a callable bound for clicked.connect().
        def emit() -> None:
            root = self.run_root()
            if root is not None:
                signal.emit(root)

        return emit


#: Verdict → row color. INTACT stays default; problems get attention.
_VERDICT_COLORS: dict[Verdict, QColor | None] = {
    Verdict.INTACT: None,
    Verdict.MISSING: QColor("#b91c1c"),
    Verdict.SIZE_MISMATCH: QColor("#b45309"),
    Verdict.HASH_MISMATCH: QColor("#b91c1c"),
    Verdict.UNREADABLE: QColor("#b45309"),
}


class ReportTable(QTableWidget):
    """One row per checked file: path, verdict, expected/actual size (§36)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(0, 4, parent)
        self.setHorizontalHeaderLabels(["Relative path", "Verdict", "Expected size", "Actual size"])
        self.horizontalHeader().setStretchLastSection(False)
        self.setColumnWidth(0, 420)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(True)

    def load_report(self, report: VerificationReport) -> None:
        """Fill from a report; problems sort to the top (§36)."""
        rows = sorted(
            report.results,
            key=lambda r: (r.verdict is Verdict.INTACT, r.relative_path),
        )
        self.setRowCount(len(rows))
        for row, item in enumerate(rows):
            expected = str(item.expected_size)
            actual = "" if item.actual_size is None else str(item.actual_size)
            values = [item.relative_path, item.verdict.value, expected, actual]
            for column, text in enumerate(values):
                cell = QTableWidgetItem(text)
                color = _VERDICT_COLORS.get(item.verdict)
                if color is not None:
                    cell.setForeground(color)
                self.setItem(row, column, cell)
