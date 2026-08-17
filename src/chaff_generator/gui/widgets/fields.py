"""Small input/display widgets shared by the GUI pages."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QLineEdit

from chaff_generator.core.errors import ChaffError
from chaff_generator.core.filesystem import free_bytes
from chaff_generator.core.size import format_size, parse_size


class AmountField(QLineEdit):
    """A size entry field ('20 MiB', '1.5 GB') validated via parse_size."""

    def __init__(self, text: str = "20 MiB", parent: object | None = None) -> None:
        super().__init__(text, parent)  # type: ignore[arg-type]
        self.setMinimumWidth(140)
        self.setPlaceholderText("e.g. 20 MiB")
        self._message = ""

    def bytes_value(self) -> int | None:
        """The parsed size in bytes, or None when the text is invalid."""
        self._message = ""
        text = self.text().strip()
        if not text:
            self._message = "Enter an amount, e.g. '20 MiB'"
            return None
        try:
            amount = parse_size(text)
        except ChaffError as exc:
            self._message = str(exc)
            return None
        if amount <= 0:
            self._message = f"Amount must be positive: {text!r}"
            return None
        return amount

    def validation_message(self) -> str:
        """The human explanation for the last invalid parse ("" when valid)."""
        return self._message

    def set_bytes(self, amount: int) -> None:
        self.setText(format_size(amount))


class FreeSpaceLabel(QLabel):
    """Live 'Free space: X' readout for a directory."""

    def __init__(self, parent: object | None = None) -> None:
        super().__init__("Free space: —", parent)  # type: ignore[arg-type]
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._path: Path | None = None

    def set_path(self, path: Path | None) -> None:
        self._path = path
        self.refresh()

    def refresh(self) -> None:
        if self._path is None:
            self.setText("Free space: —")
            return
        try:
            self.setText(f"Free space: {format_size(free_bytes(self._path))}")
        except OSError:
            self.setText("Free space: unavailable")

    def current_free_bytes(self) -> int | None:
        if self._path is None:
            return None
        try:
            return free_bytes(self._path)
        except OSError:
            return None
