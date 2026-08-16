"""Qt application bootstrap for the Chaff Generator desktop interface."""

from __future__ import annotations

from chaff_generator.version import __version__


def run() -> int:
    """Create the QApplication, show the main window, and enter the event loop.

    Returns the Qt exit code.
    """
    from PySide6.QtWidgets import QApplication, QMainWindow

    app = QApplication([])
    window = QMainWindow()
    window.setWindowTitle(f"Chaff Generator {__version__}")
    window.resize(1100, 700)
    window.show()
    return app.exec()
