"""The five primary pages (spec section 42)."""

from __future__ import annotations

from chaff_generator.gui.pages.generate import GeneratePage, PreflightDialog
from chaff_generator.gui.pages.runs import RunsPage
from chaff_generator.gui.pages.settings import SettingsPage
from chaff_generator.gui.pages.templates import ChaffBankPage
from chaff_generator.gui.pages.verify import VerifyPage

__all__ = [
    "ChaffBankPage",
    "GeneratePage",
    "PreflightDialog",
    "RunsPage",
    "SettingsPage",
    "VerifyPage",
]
