"""Main window: primary navigation over the five pages (spec section 42)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QWidget,
)

from chaff_generator.content.bank import PackManager
from chaff_generator.gui.pages import (
    ChaffBankPage,
    GeneratePage,
    RunsPage,
    SettingsPage,
    VerifyPage,
)
from chaff_generator.gui.state import RunHistory
from chaff_generator.version import __version__

#: How long closeEvent waits for a running worker before giving up (§47).
CLOSE_GRACE_MS = 5_000


class MainWindow(QMainWindow):
    """Nav list + stacked pages, wiring the pages to each other."""

    def __init__(self, history: RunHistory | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Chaff Generator {__version__}")
        self.resize(1100, 700)

        self.history = history if history is not None else RunHistory()
        self.generate_page = GeneratePage()
        self.verify_page = VerifyPage()
        self.runs_page = RunsPage(self.history)
        self.bank_page = ChaffBankPage(PackManager())
        self.settings_page = SettingsPage()

        self.stack = QStackedWidget()
        for page in (
            self.generate_page,
            self.verify_page,
            self.runs_page,
            self.bank_page,
            self.settings_page,
        ):
            self.stack.addWidget(page)

        self.nav = QListWidget()
        for label in ("Generate", "Verify", "Runs", "ChaffBank", "Settings"):
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, label)
            self.nav.addItem(item)
        self.nav.setCurrentRow(0)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setMaximumWidth(160)

        layout = QHBoxLayout()
        layout.addWidget(self.nav)
        layout.addWidget(self.stack, 1)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self._wire_pages()

    # -- cross-page wiring -----------------------------------------------------

    def _wire_pages(self) -> None:
        # Generation finished → history + Runs refresh.
        self.generate_page.run_finished.connect(self._record_generation)

        # Result card / Runs → Verify page.
        self.generate_page.verification_requested.connect(self._open_verify)
        self.runs_page.verify_requested.connect(self._open_verify)

        # Verify finished → stamp history + refresh Runs.
        self.verify_page.verification_done.connect(self._stamp_verification)

        # Runs removed from disk → refresh.
        self.generate_page.run_removed.connect(lambda _p: self.runs_page.refresh())

        # ChaffBank enable → Generate adopts the pack.
        self.bank_page.pack_enabled.connect(self._enable_pack)

    def _record_generation(self, result: object) -> None:
        from chaff_generator.core.models import GenerationResult

        assert isinstance(result, GenerationResult)
        entry = self.history.record_generation(result)
        if entry is not None:
            self.history.set_profile(
                result.run_root, self.generate_page.profile_combo.currentText()
            )
        self.runs_page.refresh()

    def _open_verify(self, run_root: Path) -> None:
        self.nav.setCurrentRow(1)
        self.verify_page.select_run(run_root)

    def _stamp_verification(self, run_root: Path, summary: str) -> None:
        self.history.record_verification(run_root, summary)
        self.runs_page.refresh()

    def _enable_pack(self, bank: object) -> None:
        from chaff_generator.content.bank import ChaffBank

        assert isinstance(bank, ChaffBank)
        self.generate_page.set_bank(bank)

    # -- shutdown (§47) ----------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:
        """§47: cancel running workers cooperatively and wait briefly."""
        running: list[QThread] = [
            worker
            for worker in (
                self.generate_page._worker,
                self.generate_page._cleanup_worker,
                self.verify_page._worker,
            )
            if worker is not None and worker.isRunning()
        ]
        for worker in running:
            cancellable = getattr(worker, "cancel", None)
            if callable(cancellable):
                cancellable()
        for worker in running:
            worker.wait(CLOSE_GRACE_MS)
        super().closeEvent(event)
