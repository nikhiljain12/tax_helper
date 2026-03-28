"""Desktop entrypoint for the PySide6 application."""

from __future__ import annotations

import sys


def main() -> int:
    """Launch the desktop redaction app."""

    try:
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise SystemExit(
            'PySide6 is required to launch the desktop app. '
            'Install desktop dependencies first.'
        ) from exc

    from PySide6.QtCore import Qt
    from app.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName('Tax PDF Redactor')
    app.setOrganizationName('Tax Helper')

    # Force light color scheme so Night Shift / system dark mode do not alter UI colors.
    try:
        app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    except AttributeError:
        pass

    window = MainWindow()
    window.show()

    return app.exec()
