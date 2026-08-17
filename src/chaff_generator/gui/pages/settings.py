"""The Settings page: persisted defaults (spec section 42)."""

from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from chaff_generator.gui.widgets import AmountField

#: Keys persisted via QSettings (per-user, per-platform storage).
KEY_TARGET = "defaults/target"
KEY_RESERVE = "defaults/reserve"
KEY_COMPLETION = "defaults/completion"


class SettingsPage(QWidget):
    """Application defaults, applied to new Generate sessions."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = QSettings("chaff-generator", "chaff-generator", self)

        box = QGroupBox("Defaults")
        form = QFormLayout(box)

        self.target_button = QPushButton(str(self.settings.value(KEY_TARGET, "")))
        self.target_button.clicked.connect(self._pick_target)
        self.reserve_field = AmountField(str(self.settings.value(KEY_RESERVE, "2 GB")))
        self.completion_combo = QComboBox()
        self.completion_combo.addItems(("keep", "delete", "trash"))
        self.completion_combo.setCurrentText(str(self.settings.value(KEY_COMPLETION, "keep")))
        # §41: keep is the safe default and must stay first.
        self.completion_combo.setCurrentIndex(
            self.completion_combo.findText(str(self.settings.value(KEY_COMPLETION, "keep")))
        )

        form.addRow("Target directory", self.target_button)
        form.addRow("Reserve", self.reserve_field)
        form.addRow("Completion action", self.completion_combo)

        save = QPushButton("Save")
        save.clicked.connect(self.save)
        layout = QVBoxLayout(self)
        layout.addWidget(box)
        layout.addStretch(1)
        layout.addWidget(save)

    def save(self) -> None:
        """Persist the defaults; invalid input is reported, not saved."""
        reserve = self.reserve_field.bytes_value()
        if reserve is None:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.critical(
                self, "Settings", f"Invalid reserve: {self.reserve_field.validation_message()}"
            )
            return
        self.settings.setValue(KEY_TARGET, self.target_button.text())
        self.settings.setValue(KEY_RESERVE, self.reserve_field.text())
        self.settings.setValue(KEY_COMPLETION, self.completion_combo.currentText())

    def _pick_target(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Choose default target directory")
        if chosen:
            self.target_button.setText(chosen)
