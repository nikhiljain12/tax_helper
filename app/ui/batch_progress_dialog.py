"""Progress dialog for batch folder redaction."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLabel, QProgressBar, QVBoxLayout


class BatchProgressDialog(QDialog):
    """Modal dialog showing per-file progress during a batch run."""

    def __init__(self, total: int, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle('Redacting Folder')
        self.setModal(True)
        self.setMinimumWidth(440)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        header = QLabel('Redacting folder...')
        header.setObjectName('sectionTitle')

        self._progress_bar = QProgressBar()
        self._progress_bar.setMinimum(0)
        self._progress_bar.setMaximum(total)
        self._progress_bar.setValue(0)
        self._progress_bar.setFormat(f'%v of {total}')

        self._file_label = QLabel('Starting...')
        self._file_label.setWordWrap(True)

        layout.addWidget(header)
        layout.addWidget(self._progress_bar)
        layout.addWidget(self._file_label)

    def update_progress(self, current_index: int, _total: int, display_name: str) -> None:
        """Slot connected to BatchFolderWorker.signals.file_started."""
        self._progress_bar.setValue(current_index)
        self._file_label.setText(f'Currently: {display_name}')

    def complete(self) -> None:
        """Set the progress bar to 100% and update the label."""
        self._progress_bar.setValue(self._progress_bar.maximum())
        self._file_label.setText('Complete!')
