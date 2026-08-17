"""Verify + cleanup workers (spec sections 45-48)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

from chaff_generator.cleanup.manager import CleanupManager
from chaff_generator.core.errors import ChaffError
from chaff_generator.core.models import CompletionAction
from chaff_generator.manifest.verifier import (
    VerificationEngine,
    VerificationMode,
)


class VerifyWorker(QThread):
    """Verifies a run off the UI thread with cooperative cancellation."""

    #: Progress. Payloads: (files_done, files_total).
    progress = Signal(int, int)
    #: The finished report. Payload: VerificationReport.
    finished_report = Signal(object)
    #: Verification could not run. Payload: error message.
    failed = Signal(str)

    def __init__(
        self,
        run_root: Path,
        mode: VerificationMode,
        *,
        sample_percent: float | None = None,
        sample_count: int | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._run_root = run_root
        self._mode = mode
        self._sample_percent = sample_percent
        self._sample_count = sample_count
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:  # pragma: no cover - exercised via the Qt event loop
        try:
            report = VerificationEngine().verify(
                self._run_root,
                self._mode,
                sample_percent=self._sample_percent,
                sample_count=self._sample_count,
                cancel_check=lambda: self._cancelled,
                progress=lambda done, total: self.progress.emit(done, total),
            )
        except ChaffError as exc:
            self.failed.emit(str(exc))
            return
        self.finished_report.emit(report)


class CleanupWorker(QThread):
    """Removes (or trashes) one validated chaff run off the UI thread."""

    #: Success. Payload: CleanupResult.
    finished_cleanup = Signal(object)
    #: Refused or failed. Payload: error message.
    failed = Signal(str)

    def __init__(
        self, run_root: Path, mode: CompletionAction, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._run_root = run_root
        self._mode = mode

    def run(self) -> None:  # pragma: no cover - exercised via the Qt event loop
        try:
            result = CleanupManager().clean(self._run_root, self._mode)
        except ChaffError as exc:
            self.failed.emit(str(exc))
            return
        self.finished_cleanup.emit(result)
