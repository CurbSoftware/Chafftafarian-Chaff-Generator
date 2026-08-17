"""The active-generation view (spec section 45)."""

from __future__ import annotations

import time

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from chaff_generator.core.events import (
    FileStarted,
    ProgressUpdated,
    WarningRaised,
)
from chaff_generator.core.size import format_size


class ProgressPanel(QWidget):
    """Live progress for one running generation job.

    Displays overall progress, bytes/target, file count, current file and
    type, throughput, elapsed, ETA, free space, and warnings, with
    Pause/Resume/Cancel controls. The GUI stays responsive: all numbers
    arrive as queued signal updates from the worker thread.
    """

    paused_state_changed = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._started_at: float | None = None
        self._target: int | None = None
        self._written = 0
        self._throughput = 0.0

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)

        self.bytes_label = QLabel("0 B written")
        self.files_label = QLabel("Files: 0")
        self.current_label = QLabel("Current file: —")
        self.throughput_label = QLabel("Throughput: —")
        self.eta_label = QLabel("ETA: —")
        self.free_label = QLabel("Free space: —")
        self.warning_label = QLabel("")
        self.warning_label.setWordWrap(True)
        self.warning_label.setVisible(False)

        stats = QVBoxLayout()
        for widget in (
            self.bytes_label,
            self.files_label,
            self.current_label,
            self.throughput_label,
            self.eta_label,
            self.free_label,
            self.warning_label,
        ):
            stats.addWidget(widget)

        box = QGroupBox("Generating chaff")
        layout = QVBoxLayout(box)
        layout.addWidget(self.bar)
        layout.addLayout(stats)
        # The group box is the only visible child; keep the layout flat.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(box)

        self.pause_button = QPushButton("Pause")
        self.resume_button = QPushButton("Resume")
        self.resume_button.setEnabled(False)
        self.cancel_button = QPushButton("Cancel")
        controls = QHBoxLayout()
        controls.addWidget(self.pause_button)
        controls.addWidget(self.resume_button)
        controls.addStretch(1)
        controls.addWidget(self.cancel_button)
        layout.addLayout(controls)

        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(500)
        self._elapsed_timer.timeout.connect(self._tick)

    # -- lifecycle --------------------------------------------------------

    def begin(self) -> None:
        """Reset all fields for a fresh run and start the elapsed clock."""
        self._started_at = time.monotonic()
        self._target = None
        self._written = 0
        self._throughput = 0.0
        self.bar.setValue(0)
        self.bytes_label.setText("0 B written")
        self.files_label.setText("Files: 0")
        self.current_label.setText("Current file: —")
        self.throughput_label.setText("Throughput: —")
        self.eta_label.setText("ETA: —")
        self.warning_label.setVisible(False)
        self.pause_button.setEnabled(True)
        self.resume_button.setEnabled(False)
        self._elapsed_timer.start()

    def end(self) -> None:
        """Stop the clock when the run finishes."""
        self._tick()
        self._elapsed_timer.stop()
        self.pause_button.setEnabled(False)
        self.resume_button.setEnabled(False)

    # -- event adaptation --------------------------------------------------

    def on_event(self, event: object) -> None:
        if isinstance(event, ProgressUpdated):
            self.on_progress(event)
        elif isinstance(event, FileStarted):
            self.current_label.setText(f"Current file: {event.relative_path} ({event.renderer})")
        elif isinstance(event, WarningRaised):
            self._add_warning(event.message)

    def on_progress(self, event: ProgressUpdated) -> None:
        self._target = event.target_bytes
        self._written = event.bytes_written
        self._throughput = event.throughput_bps
        self.bytes_label.setText(
            f"{format_size(event.bytes_written)} written"
            + (f" of {format_size(event.target_bytes)}" if event.target_bytes else "")
        )
        self.files_label.setText(f"Files: {event.files:,}")
        self.free_label.setText(f"Free space: {format_size(event.free_bytes)}")
        self.throughput_label.setText(f"Throughput: {format_size(int(event.throughput_bps))}/s")
        if event.target_bytes:
            self.bar.setValue(min(100, int(event.bytes_written * 100 / event.target_bytes)))
        self._tick()

    def set_paused(self, paused: bool) -> None:
        self.pause_button.setEnabled(not paused)
        self.resume_button.setEnabled(paused)
        self.paused_state_changed.emit(paused)

    # -- internals ----------------------------------------------------------

    def _add_warning(self, message: str) -> None:
        existing = self.warning_label.text()
        combined = message if not existing else f"{existing}\n{message}"
        self.warning_label.setText(combined)
        self.warning_label.setVisible(True)

    def _tick(self) -> None:
        if self._started_at is None:
            return
        elapsed = max(time.monotonic() - self._started_at, 0.0)
        minutes, seconds = divmod(int(elapsed), 60)
        text = f"Elapsed: {minutes}:{seconds:02d}"
        if self._target and self._throughput > 1:
            left = max(self._target - self._written, 0)
            eta = left / self._throughput
            eta_min, eta_sec = divmod(int(eta), 60)
            text += f"   ETA: {eta_min}:{eta_sec:02d}"
        self.eta_label.setText(text)
