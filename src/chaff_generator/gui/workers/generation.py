"""Generation worker: owns the engine on a QThread (spec sections 45-46).

The engine's event callback fires on the worker thread; re-emitting the
event through a Qt signal auto-queues it onto the UI thread, so pages can
connect directly without locks.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal

from chaff_generator.content.bank import ChaffBank
from chaff_generator.core.engine import ChaffEngine
from chaff_generator.core.errors import ChaffError
from chaff_generator.core.events import ChaffEvent, RunCompleted
from chaff_generator.core.models import GenerationConfig, PreflightSummary


class GenerationWorker(QThread):
    """Runs one generation job off the UI thread (spec section 45)."""

    #: Every engine event, queued to the UI thread. Payload: ChaffEvent.
    engine_event = Signal(object)
    #: The final result. Payload: GenerationResult.
    finished_run = Signal(object)
    #: Job could not run at all. Payload: error message.
    failed = Signal(str)

    def __init__(
        self,
        config: GenerationConfig,
        bank: ChaffBank | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._engine = ChaffEngine(config, bank=bank, event_callback=self._on_event)

    def preflight(self) -> PreflightSummary:
        """Cheap preflight checks (safe to call before or without start())."""
        return self._engine.preflight()

    # -- control slots (thread-safe: they only set flags on the engine) ------

    def pause(self) -> None:
        self._engine.pause()

    def resume(self) -> None:
        self._engine.resume()

    def cancel(self) -> None:
        self._engine.cancel()

    # -- QThread --------------------------------------------------------------

    def run(self) -> None:  # pragma: no cover - exercised via the Qt event loop
        try:
            result = self._engine.generate()
        except ChaffError as exc:
            self.failed.emit(str(exc))
            return
        except OSError as exc:
            self.failed.emit(f"Filesystem error: {exc}")
            return
        self.finished_run.emit(result)

    def _on_event(self, event: ChaffEvent) -> None:
        if isinstance(event, RunCompleted) and event.result is not None:
            # The result arrives on finished_run instead; avoid duplication.
            return
        self.engine_event.emit(event)
