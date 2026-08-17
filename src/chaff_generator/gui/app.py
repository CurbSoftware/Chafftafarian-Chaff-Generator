"""Qt application bootstrap for the Chaff Generator desktop interface."""

from __future__ import annotations

from chaff_generator.version import __version__


def run() -> int:
    """Create the QApplication, show the main window, and enter the event loop.

    Returns the Qt exit code.
    """
    from PySide6.QtWidgets import QApplication

    from chaff_generator.gui.main_window import MainWindow

    app = QApplication([])
    app.setApplicationName("Chaff Generator")
    app.setOrganizationName("chaff-generator")
    app.setApplicationVersion(__version__)
    window = MainWindow()
    window.show()
    return app.exec()
