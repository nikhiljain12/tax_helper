"""Shared progress dialog for long-running operations."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QProgressDialog, QWidget


class BusyProgressDialog(QProgressDialog):
    """A non-cancelable indeterminate progress dialog."""

    def __init__(self, label_text: str, parent: QWidget | None = None) -> None:
        super().__init__(label_text, None, 0, 0, parent)
        self.setWindowTitle('Working')
        self.setWindowModality(Qt.WindowModal)
        self.setCancelButton(None)
        self.setMinimumDuration(0)
        self.setValue(0)
