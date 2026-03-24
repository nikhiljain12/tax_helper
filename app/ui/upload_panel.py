"""Upload and options screen for the desktop application."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
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
    batch_requested = Signal(Path, Path)  # (input_folder, output_folder)

    def __init__(self) -> None:
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(18)

        title = QLabel('Tax PDF Redactor')
        title.setObjectName('screenTitle')

        privacy_note = QLabel('Files never leave your computer.')
        privacy_note.setObjectName('privacyNote')

        # --- Mode toggle ---
        self._single_file_btn = QPushButton('Single File')
        self._single_file_btn.setCheckable(True)
        self._single_file_btn.setChecked(True)

        self._batch_folder_btn = QPushButton('Batch Folder')
        self._batch_folder_btn.setCheckable(True)

        self._mode_group = QButtonGroup(self)
        self._mode_group.addButton(self._single_file_btn)
        self._mode_group.addButton(self._batch_folder_btn)
        self._mode_group.setExclusive(True)
        self._mode_group.buttonClicked.connect(self._on_mode_changed)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(0)
        mode_row.addWidget(self._single_file_btn)
        mode_row.addWidget(self._batch_folder_btn)
        mode_row.addStretch(1)

        # --- Single file widgets ---
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

        self._single_file_widget = QWidget()
        sf_layout = QVBoxLayout(self._single_file_widget)
        sf_layout.setContentsMargins(0, 0, 0, 0)
        sf_layout.setSpacing(8)
        sf_layout.addWidget(self.drop_area)
        sf_layout.addLayout(file_controls)

        # --- Batch folder widgets ---
        self._input_folder_edit = QLineEdit()
        self._input_folder_edit.setPlaceholderText('Select input folder...')
        self._input_folder_edit.setReadOnly(True)

        input_browse_btn = QPushButton('Browse...')
        input_browse_btn.clicked.connect(self.choose_input_folder)

        input_row = QHBoxLayout()
        input_row.addWidget(QLabel('Input folder:'))
        input_row.addWidget(self._input_folder_edit, 1)
        input_row.addWidget(input_browse_btn)

        self._output_folder_edit = QLineEdit()
        self._output_folder_edit.setPlaceholderText('Default: <input_folder>/redacted/')
        self._output_folder_edit.setReadOnly(True)

        output_browse_btn = QPushButton('Browse...')
        output_browse_btn.clicked.connect(self.choose_output_folder)

        output_clear_btn = QPushButton('Clear')
        output_clear_btn.clicked.connect(self._output_folder_edit.clear)

        output_row = QHBoxLayout()
        output_row.addWidget(QLabel('Output folder:'))
        output_row.addWidget(self._output_folder_edit, 1)
        output_row.addWidget(output_browse_btn)
        output_row.addWidget(output_clear_btn)

        self._batch_folder_widget = QWidget()
        bf_layout = QVBoxLayout(self._batch_folder_widget)
        bf_layout.setContentsMargins(0, 0, 0, 0)
        bf_layout.setSpacing(8)
        bf_layout.addLayout(input_row)
        bf_layout.addLayout(output_row)
        self._batch_folder_widget.setVisible(False)

        # --- Shared options form (unchanged) ---
        form_title = QLabel('Redaction options')
        form_title.setObjectName('sectionTitle')

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignTop)
        form_layout.setFormAlignment(Qt.AlignTop)
        form_layout.setSpacing(12)

        self.names_input = self._build_text_input('One entry per line, for example:\nJohn Doe')
        self.addresses_input = self._build_text_input('One entry per line, for example:\n123 Main Street')
        self.tins_input = self._build_text_input('One entry per line, for example:\n123-45-6789')
        self.custom_input = self._build_text_input('One entry per line for any additional exact values')

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
        self.find_matches_button.clicked.connect(self._on_primary_action)

        layout.addWidget(title)
        layout.addWidget(privacy_note)
        layout.addLayout(mode_row)
        layout.addWidget(self._single_file_widget)
        layout.addWidget(self._batch_folder_widget)
        layout.addWidget(form_title)
        layout.addLayout(form_layout)
        layout.addWidget(detect_title)
        layout.addLayout(detect_layout)
        layout.addWidget(self.case_sensitive_checkbox)
        layout.addStretch(1)
        layout.addWidget(self.find_matches_button, 0, Qt.AlignRight)

    def _on_mode_changed(self, _button=None) -> None:
        is_batch = self._batch_folder_btn.isChecked()
        self._single_file_widget.setVisible(not is_batch)
        self._batch_folder_widget.setVisible(is_batch)
        self.find_matches_button.setText('Redact Folder' if is_batch else 'Find Matches')

    def _on_primary_action(self) -> None:
        if self._batch_folder_btn.isChecked():
            self._emit_batch_requested()
        else:
            self.analyze_requested.emit()

    def _emit_batch_requested(self) -> None:
        input_path_str = self._input_folder_edit.text().strip()
        if not input_path_str:
            QMessageBox.warning(self, 'Tax PDF Redactor', 'Please select an input folder.')
            return

        input_folder = Path(input_path_str)
        if not input_folder.is_dir():
            QMessageBox.warning(self, 'Tax PDF Redactor', 'Input folder does not exist.')
            return

        output_path_str = self._output_folder_edit.text().strip()
        output_folder = Path(output_path_str) if output_path_str else input_folder / 'redacted'

        self.batch_requested.emit(input_folder, output_folder)

    def choose_input_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, 'Choose Input Folder')
        if folder:
            self._input_folder_edit.setText(folder)

    def choose_output_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, 'Choose Output Folder')
        if folder:
            self._output_folder_edit.setText(folder)

    def set_batch_input_folder(self, folder: str) -> None:
        """Switch to batch mode and set the input folder path."""
        self._batch_folder_btn.setChecked(True)
        self._on_mode_changed()
        self._input_folder_edit.setText(folder)

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
        self._input_folder_edit.clear()
        self._output_folder_edit.clear()
        self._single_file_btn.setChecked(True)
        self._on_mode_changed()

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
