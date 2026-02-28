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

    from app.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName('Tax PDF Redactor')
    app.setOrganizationName('Tax Helper')

    window = MainWindow()
    window.show()

    return app.exec()
