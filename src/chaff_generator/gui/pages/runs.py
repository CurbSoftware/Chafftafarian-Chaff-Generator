"""The Runs page: lightweight local history (spec section 49)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from chaff_generator.core.size import format_size
from chaff_generator.gui.state import HistoryEntry, RunHistory


class RunsPage(QWidget):
    """Recent runs from the local JSON history (manifests stay authoritative)."""

    #: Ask the main window to open this run in the Verify page.
    verify_requested = Signal(Path)
    #: The user removed a run from disk through this page.
    run_removed = Signal(Path)

    def __init__(self, history: RunHistory, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.history = history

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Run", "Path", "Date", "Size", "Files", "Status", "Last verification"]
        )
        self.table.setColumnWidth(0, 240)
        self.table.setColumnWidth(1, 420)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(lambda _i: self._verify_selected())

        self.verify_button = QPushButton("Verify…")
        self.open_button = QPushButton("Open Folder")
        self.remove_entry = QPushButton("Remove from History")
        self.verify_button.clicked.connect(self._verify_selected)
        self.open_button.clicked.connect(self._open_selected)
        self.remove_entry.clicked.connect(self._remove_selected)

        buttons = QHBoxLayout()
        for button in (self.verify_button, self.open_button, self.remove_entry):
            buttons.addWidget(button)
        buttons.addStretch(1)

        note = QLabel(
            "History is a convenience index; the authoritative record of each run is its manifest."
        )
        note.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.addLayout(buttons)
        layout.addWidget(note)
        self.refresh()

    # -- population -----------------------------------------------------------

    def refresh(self) -> None:
        entries = self.history.entries()
        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            values = [
                entry.run_id,
                entry.path,
                entry.date,
                format_size(entry.size_bytes),
                f"{entry.file_count:,}",
                entry.status,
                entry.last_verification or "—",
            ]
            for column, text in enumerate(values):
                cell = QTableWidgetItem(text)
                cell.setToolTip(text)
                self.table.setItem(row, column, cell)

    # -- actions ---------------------------------------------------------------

    def _selected_entry(self) -> HistoryEntry | None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        row = selected[0].row()
        entries = self.history.entries()
        return entries[row] if row < len(entries) else None

    def _verify_selected(self) -> None:
        entry = self._selected_entry()
        if entry is not None:
            self.verify_requested.emit(Path(entry.path))

    def _open_selected(self) -> None:
        entry = self._selected_entry()
        if entry is None or not Path(entry.path).is_dir():
            return
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        QDesktopServices.openUrl(QUrl.fromLocalFile(entry.path))

    def _remove_selected(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            return
        # Removes the *history entry* only — never files on disk.
        self.history.remove(Path(entry.path))
        self.refresh()
