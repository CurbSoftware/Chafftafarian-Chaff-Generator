"""The ChaffBank page: pack management and template preview (§50-§51)."""

from __future__ import annotations

import random
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from chaff_generator.content.bank import (
    ChaffBank,
    PackManager,
    default_pack_path,
    validate_pack,
)
from chaff_generator.content.template_engine import ChaffTemplateEngine
from chaff_generator.content.world import build_world
from chaff_generator.core.errors import ChaffError, TemplateError
from chaff_generator.core.models import GenerationConfig, TargetMode, TargetSpec


def _preview_config(seed: int) -> GenerationConfig:
    """A minimal config for building preview worlds (nothing is written)."""
    return GenerationConfig(
        schema_version=1,
        target=TargetSpec(path=Path("/nonexistent-preview"), mode=TargetMode.EXACT, amount=1),
        seed=seed,
    )


class ChaffBankPage(QWidget):
    """Installed packs + the template preview sandbox (no marketplace, §50)."""

    #: The user enabled a different pack; Generate adopts it.
    pack_enabled = Signal(object)  # payload: ChaffBank

    def __init__(self, pack_manager: PackManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.manager = pack_manager
        self._active_id = ""  # the builtin default starts active
        self._bank: ChaffBank = ChaffBank.load(default_pack_path())

        # -- installed packs (§50) -----------------------------------------
        packs_box = QGroupBox("Installed packs")
        packs_layout = QVBoxLayout(packs_box)
        self.packs_table = QTableWidget(0, 6)
        self.packs_table.setHorizontalHeaderLabels(
            ["Name", "ID", "Version", "Language", "Status", "Location"]
        )
        self.packs_table.setColumnWidth(0, 200)
        self.packs_table.setColumnWidth(1, 140)
        self.packs_table.setColumnWidth(5, 420)
        self.packs_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.packs_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.packs_table.itemSelectionChanged.connect(self._selection_changed)
        packs_layout.addWidget(self.packs_table)

        self.validate_button = QPushButton("Validate")
        self.enable_button = QPushButton("Enable")
        self.import_button = QPushButton("Import Pack (ZIP)…")
        self.folder_button = QPushButton("Open Folder")
        self.validate_button.clicked.connect(self._validate)
        self.enable_button.clicked.connect(self._enable)
        self.import_button.clicked.connect(self._import_zip)
        self.folder_button.clicked.connect(self._open_folder)
        buttons = QHBoxLayout()
        for button in (
            self.validate_button,
            self.enable_button,
            self.import_button,
            self.folder_button,
        ):
            buttons.addWidget(button)
        buttons.addStretch(1)
        packs_layout.addLayout(buttons)

        # -- template preview (§51) ------------------------------------------
        preview_box = QGroupBox("Template preview")
        preview_form = QFormLayout(preview_box)
        self.template_combo = QComboBox()
        self.seed_edit = QLineEdit("481925")
        preview_form.addRow("Template", self.template_combo)
        preview_form.addRow("Seed", self.seed_edit)
        self.preview_output = QPlainTextEdit()
        self.preview_output.setReadOnly(True)
        preview_form.addRow(self.preview_output)
        self.preview_button = QPushButton("Preview")
        self.preview_button.clicked.connect(self._preview)
        row = QHBoxLayout()
        row.addWidget(self.preview_button)
        row.addStretch(1)
        preview_form.addRow(row)

        layout = QVBoxLayout(self)
        layout.addWidget(packs_box)
        layout.addWidget(preview_box, 1)
        self._load_preview_bank(self._bank)
        self.refresh()

    # -- packs ------------------------------------------------------------------

    def refresh(self) -> None:
        packs = self.manager.list_packs()
        self.packs_table.setRowCount(len(packs))
        for row, info in enumerate(packs):
            status = "enabled" if info.manifest.id == self._active_id else "available"
            values = [
                info.manifest.name,
                info.manifest.id,
                info.manifest.version,
                info.manifest.language,
                status,
                str(info.path),
            ]
            for column, text in enumerate(values):
                cell = QTableWidgetItem(text)
                cell.setToolTip(text)
                self.packs_table.setItem(row, column, cell)

    def _selected(self) -> Path | None:
        selected = self.packs_table.selectionModel().selectedRows()
        if not selected:
            return None
        row = selected[0].row()
        item = self.packs_table.item(row, 5)
        return Path(item.text()) if item is not None else None

    def _selection_changed(self) -> None:
        """Preview templates come from the selected pack (or the active one)."""
        path = self._selected()
        bank = self._bank
        if path is not None:
            try:
                bank = ChaffBank.load(path)
            except ChaffError:
                return  # invalid selection; keep the current preview set
        self._load_preview_bank(bank)

    def _load_preview_bank(self, bank: ChaffBank) -> None:
        self._bank = bank
        current = self.template_combo.currentData()
        self.template_combo.clear()
        for template in sorted(bank.templates().all(), key=lambda t: t.id):
            self.template_combo.addItem(f"{template.id} ({template.kind})", template.id)
        if current is not None:
            index = self.template_combo.findData(current)
            if index >= 0:
                self.template_combo.setCurrentIndex(index)

    def set_active_bank(self, bank: ChaffBank) -> None:
        """Adopt the bank enabled elsewhere (kept in sync with Generate)."""
        self._active_id = bank.manifest.id
        self._load_preview_bank(bank)
        self.refresh()

    def _validate(self) -> None:
        path = self._selected()
        if path is None:
            return
        try:
            report = validate_pack(path)
        except ChaffError as exc:
            QMessageBox.critical(self, "ChaffBank", f"Pack invalid:\n{exc}")
            return
        if report.ok:
            body = "Pack is valid."
            if report.warnings:
                body += "\nWarnings:\n" + "\n".join(f"- {w}" for w in report.warnings)
            QMessageBox.information(self, "ChaffBank", body)
        else:
            QMessageBox.warning(
                self, "ChaffBank", "Pack is invalid:\n" + "\n".join(f"- {e}" for e in report.errors)
            )

    def _enable(self) -> None:
        path = self._selected()
        if path is None:
            return
        try:
            bank = ChaffBank.load(path)
        except ChaffError as exc:
            QMessageBox.critical(self, "ChaffBank", f"Cannot enable pack:\n{exc}")
            return
        self._active_id = bank.manifest.id
        self.refresh()
        self.pack_enabled.emit(bank)

    def _import_zip(self) -> None:
        chosen, _filter = QFileDialog.getOpenFileName(
            self, "Import pack", "", "Pack archive (*.zip)"
        )
        if not chosen:
            return
        try:
            info = self.manager.import_zip(Path(chosen))
        except ChaffError as exc:
            QMessageBox.critical(
                self, "ChaffBank", f"Import refused (the archive was not installed):\n{exc}"
            )
            return
        self.refresh()
        QMessageBox.information(
            self, "ChaffBank", f"Imported {info.manifest.name} {info.manifest.version}."
        )

    def _open_folder(self) -> None:
        path = self._selected()
        if path is None or not path.is_dir():
            return
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    # -- template preview (§51) ---------------------------------------------------

    def _preview(self) -> None:
        template_id = self.template_combo.currentData()
        if template_id is None:
            return
        try:
            seed = int(self.seed_edit.text().strip() or "0")
        except ValueError:
            QMessageBox.critical(self, "Template preview", "Seed must be an integer.")
            return

        template = self._bank.templates().get(template_id)
        if template is None:
            return
        rng = random.Random(seed)
        try:
            world = build_world(seed, _preview_config(seed), self._bank, estimated_files=20)
            engine = ChaffTemplateEngine(world=world, bank=self._bank, rng=rng)
            output = engine.render_template(template)
        except TemplateError as exc:
            # TemplateError already carries the did-you-mean hint (§51).
            self.preview_output.setPlainText(f"TEMPLATE ERROR\n\n{exc}")
            return
        except ChaffError as exc:
            self.preview_output.setPlainText(f"ERROR\n\n{exc}")
            return
        self.preview_output.setPlainText(output)
