from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from .main_window import MainWindow
from .theme import apply_theme


def create_application(argv: list[str] | None = None) -> QApplication:
    app = QApplication.instance() or QApplication(argv or ["ultra3-editor"])
    app.setApplicationName("Ultra3 Lab")
    app.setOrganizationName("Ultra3 Lab")
    apply_theme(app)
    return app


def run() -> int:
    app = create_application(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()
