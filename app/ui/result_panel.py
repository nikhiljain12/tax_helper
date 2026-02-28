"""Success screen shown after redaction completes."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.core.models import RedactionResult


class ResultPanel(QWidget):
    """Displays the final output after redactions are saved."""

    def __init__(self) -> None:
        super().__init__()

        self._output_path = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)

        title = QLabel('Redaction Complete')
        title.setObjectName('screenTitle')

        self.result_label = QLabel('No file has been generated yet.')
        self.result_label.setWordWrap(True)

        button_row = QHBoxLayout()
        button_row.setSpacing(12)

        self.open_file_button = QPushButton('Open File')
        self.open_folder_button = QPushButton('Open Folder')
        self.reset_button = QPushButton('Redact Another PDF')

        button_row.addWidget(self.open_file_button)
        button_row.addWidget(self.open_folder_button)
        button_row.addStretch(1)
        button_row.addWidget(self.reset_button)

        layout.addWidget(title)
        layout.addWidget(self.result_label, 0, Qt.AlignTop)
        layout.addStretch(1)
        layout.addLayout(button_row)

    def set_result(self, result: RedactionResult) -> None:
        """Render the final save path and annotation count."""

        self._output_path = result.output_path
        self.result_label.setText(
            f'Saved {result.redaction_count} redaction annotation(s) to:\n'
            f'{result.output_path}'
        )
