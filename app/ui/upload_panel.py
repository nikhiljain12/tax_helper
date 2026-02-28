"""Upload and options screen for the desktop application."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.models import PDFFileInfo


class DropArea(QFrame):
    """Drag-and-drop PDF target."""

    file_dropped = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setObjectName('dropArea')

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(8)

        title = QLabel('Drop a PDF here')
        title.setAlignment(Qt.AlignCenter)
        title.setObjectName('dropAreaTitle')

        subtitle = QLabel('or use the button below to choose a file')
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if self._has_pdf(event):
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802
        urls = event.mimeData().urls()
        if not urls:
            event.ignore()
            return

        local_file = urls[0].toLocalFile()
        if local_file.lower().endswith('.pdf'):
            self.file_dropped.emit(local_file)
            event.acceptProposedAction()
            return

        event.ignore()

    def _has_pdf(self, event) -> bool:
        for url in event.mimeData().urls():
            if url.isLocalFile() and url.toLocalFile().lower().endswith('.pdf'):
                return True
        return False


class UploadPanel(QWidget):
    """The first screen in the desktop workflow."""

    choose_pdf_requested = Signal()
    analyze_requested = Signal()

    def __init__(self) -> None:
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(18)

        title = QLabel('Tax PDF Redactor')
        title.setObjectName('screenTitle')

        privacy_note = QLabel('Files never leave your computer.')
        privacy_note.setObjectName('privacyNote')

        self.drop_area = DropArea()
        self.drop_area.setMinimumHeight(160)

        self.choose_pdf_button = QPushButton('Choose PDF')
        self.choose_pdf_button.clicked.connect(self.choose_pdf_requested.emit)

        self.file_summary_label = QLabel('No PDF selected')
        self.file_summary_label.setWordWrap(True)

        file_controls = QHBoxLayout()
        file_controls.setSpacing(12)
        file_controls.addWidget(self.choose_pdf_button, 0)
        file_controls.addWidget(self.file_summary_label, 1)

        form_title = QLabel('Redaction options')
        form_title.setObjectName('sectionTitle')

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignTop)
        form_layout.setFormAlignment(Qt.AlignTop)
        form_layout.setSpacing(12)

        self.names_input = self._build_text_input(
            'One entry per line, for example:\nJohn Doe'
        )
        self.addresses_input = self._build_text_input(
            'One entry per line, for example:\n123 Main Street'
        )
        self.tins_input = self._build_text_input(
            'One entry per line, for example:\n123-45-6789'
        )
        self.custom_input = self._build_text_input(
            'One entry per line for any additional exact values'
        )

        form_layout.addRow('Names', self.names_input)
        form_layout.addRow('Addresses', self.addresses_input)
        form_layout.addRow('TIN / SSN / EIN', self.tins_input)
        form_layout.addRow('Custom text', self.custom_input)

        detect_title = QLabel('Auto-detect')
        detect_title.setObjectName('sectionTitle')

        detect_layout = QHBoxLayout()
        detect_layout.setSpacing(16)

        self.detect_tin_checkbox = QCheckBox('TIN / SSN / EIN patterns')
        self.detect_phone_checkbox = QCheckBox('Phone')
        self.detect_email_checkbox = QCheckBox('Email')
        self.case_sensitive_checkbox = QCheckBox('Case-sensitive exact matching')

        detect_layout.addWidget(self.detect_tin_checkbox)
        detect_layout.addWidget(self.detect_phone_checkbox)
        detect_layout.addWidget(self.detect_email_checkbox)
        detect_layout.addStretch(1)

        self.find_matches_button = QPushButton('Find Matches')
        self.find_matches_button.setObjectName('primaryButton')
        self.find_matches_button.clicked.connect(self.analyze_requested.emit)

        layout.addWidget(title)
        layout.addWidget(privacy_note)
        layout.addWidget(self.drop_area)
        layout.addLayout(file_controls)
        layout.addWidget(form_title)
        layout.addLayout(form_layout)
        layout.addWidget(detect_title)
        layout.addLayout(detect_layout)
        layout.addWidget(self.case_sensitive_checkbox)
        layout.addStretch(1)
        layout.addWidget(self.find_matches_button, 0, Qt.AlignRight)

    def set_file_info(self, file_info: PDFFileInfo | None) -> None:
        """Update the selected file summary."""

        if file_info is None:
            self.file_summary_label.setText('No PDF selected')
            return

        self.file_summary_label.setText(
            f'{file_info.path.name}  |  '
            f'{self._format_bytes(file_info.file_size_bytes)}  |  '
            f'{file_info.page_count} page(s)\n'
            f'{file_info.path}'
        )

    def collect_options(self) -> dict[str, object]:
        """Return the current UI state for request building."""

        return {
            'names': self.names_input.toPlainText(),
            'addresses': self.addresses_input.toPlainText(),
            'tins': self.tins_input.toPlainText(),
            'custom_strings': self.custom_input.toPlainText(),
            'detect_tin': self.detect_tin_checkbox.isChecked(),
            'detect_phone': self.detect_phone_checkbox.isChecked(),
            'detect_email': self.detect_email_checkbox.isChecked(),
            'case_sensitive': self.case_sensitive_checkbox.isChecked(),
        }

    def clear_state(self) -> None:
        """Reset the form for the next document."""

        self.set_file_info(None)
        self.names_input.clear()
        self.addresses_input.clear()
        self.tins_input.clear()
        self.custom_input.clear()
        self.detect_tin_checkbox.setChecked(False)
        self.detect_phone_checkbox.setChecked(False)
        self.detect_email_checkbox.setChecked(False)
        self.case_sensitive_checkbox.setChecked(False)

    def _build_text_input(self, placeholder: str) -> QPlainTextEdit:
        text_edit = QPlainTextEdit()
        text_edit.setPlaceholderText(placeholder)
        text_edit.setFixedHeight(72)
        return text_edit

    def _format_bytes(self, size_bytes: int) -> str:
        value = float(size_bytes)
        units = ['B', 'KB', 'MB', 'GB']
        unit = units[0]

        for unit in units:
            if value < 1024 or unit == units[-1]:
                break
            value /= 1024

        if unit == 'B':
            return f'{int(value)} {unit}'
        return f'{value:.1f} {unit}'
