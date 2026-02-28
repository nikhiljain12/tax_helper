"""Main window for the desktop PDF redaction application."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThreadPool, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
)

from app.core.models import DocumentAnalysis, PDFFileInfo, RedactionResult
from app.core.redaction_engine import RedactionEngine
from app.services.file_service import FileService
from app.services.redaction_workflow import RedactionWorkflowService
from app.ui.progress_dialog import BusyProgressDialog
from app.ui.result_panel import ResultPanel
from app.ui.review_panel import ReviewPanel
from app.ui.upload_panel import UploadPanel
from app.ui.workers import AnalyzeWorker, ApplyWorker


class MainWindow(QMainWindow):
    """Single-window desktop UI for local PDF redaction."""

    def __init__(self) -> None:
        super().__init__()

        self.engine = RedactionEngine()
        self.workflow = RedactionWorkflowService()
        self.file_service = FileService()
        self.thread_pool = QThreadPool.globalInstance()

        self.current_file_info: PDFFileInfo | None = None
        self.current_analysis: DocumentAnalysis | None = None
        self.current_result: RedactionResult | None = None
        self.progress_dialog: BusyProgressDialog | None = None

        self.setWindowTitle('Tax PDF Redactor')
        self.resize(1100, 780)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.upload_panel = UploadPanel()
        self.review_panel = ReviewPanel()
        self.result_panel = ResultPanel()

        self.stack.addWidget(self.upload_panel)
        self.stack.addWidget(self.review_panel)
        self.stack.addWidget(self.result_panel)

        self.upload_panel.choose_pdf_requested.connect(self.choose_pdf)
        self.upload_panel.drop_area.file_dropped.connect(self.load_pdf)
        self.upload_panel.analyze_requested.connect(self.start_analysis)

        self.review_panel.back_button.clicked.connect(self.show_upload)
        self.review_panel.save_button.clicked.connect(self.save_redacted_pdf)

        self.result_panel.open_file_button.clicked.connect(self.open_result_file)
        self.result_panel.open_folder_button.clicked.connect(self.open_result_folder)
        self.result_panel.reset_button.clicked.connect(self.reset_flow)

        self._apply_styles()

    def choose_pdf(self) -> None:
        """Open the native file picker."""

        filename, _ = QFileDialog.getOpenFileName(
            self,
            'Choose PDF',
            str(Path.home()),
            'PDF Files (*.pdf)',
        )
        if filename:
            self.load_pdf(filename)

    def load_pdf(self, file_path: str) -> None:
        """Validate and store a chosen PDF file."""

        try:
            file_info = self.file_service.describe_pdf(file_path)
        except Exception as exc:
            self._show_error(str(exc))
            return

        self.current_file_info = file_info
        self.current_analysis = None
        self.current_result = None
        self.upload_panel.set_file_info(file_info)
        self.stack.setCurrentWidget(self.upload_panel)

    def start_analysis(self) -> None:
        """Build a request and analyze the selected PDF."""

        if self.current_file_info is None:
            self._show_error('Choose a PDF before searching for matches.')
            return

        options = self.upload_panel.collect_options()

        try:
            request = self.workflow.build_request(
                input_path=self.current_file_info.path,
                names=self.workflow.parse_multivalue_text(options['names']),
                addresses=self.workflow.parse_multivalue_text(options['addresses']),
                tins=self.workflow.parse_multivalue_text(options['tins']),
                custom_strings=self.workflow.parse_multivalue_text(
                    options['custom_strings']
                ),
                detect_tin=bool(options['detect_tin']),
                detect_phone=bool(options['detect_phone']),
                detect_email=bool(options['detect_email']),
                case_sensitive=bool(options['case_sensitive']),
            )
        except ValueError as exc:
            self._show_error(str(exc))
            return

        self._show_progress('Analyzing PDF for matches...')
        worker = AnalyzeWorker(self.engine, request)
        worker.signals.completed.connect(self._handle_analysis_complete)
        worker.signals.failed.connect(self._handle_worker_failure)
        self.thread_pool.start(worker)

    def save_redacted_pdf(self) -> None:
        """Save the selected redactions to a new PDF."""

        if self.current_file_info is None or self.current_analysis is None:
            self._show_error('Run an analysis before saving.')
            return

        selected_ids = self.review_panel.selected_match_ids()
        if not selected_ids:
            self._show_error('Select at least one match before saving.')
            return

        default_path = self.workflow.default_output_path(self.current_file_info.path)
        output_path_str, _ = QFileDialog.getSaveFileName(
            self,
            'Save Redacted PDF',
            str(default_path),
            'PDF Files (*.pdf)',
        )

        if not output_path_str:
            return

        output_path = Path(output_path_str)
        if output_path.suffix.lower() != '.pdf':
            output_path = output_path.with_suffix('.pdf')

        self._show_progress('Applying redactions and saving PDF...')
        worker = ApplyWorker(
            engine=self.engine,
            input_path=self.current_file_info.path,
            matches=self.current_analysis.matches,
            selected_match_ids=selected_ids,
            output_path=output_path,
        )
        worker.signals.completed.connect(self._handle_apply_complete)
        worker.signals.failed.connect(self._handle_worker_failure)
        self.thread_pool.start(worker)

    def open_result_file(self) -> None:
        """Open the generated PDF."""

        if self.current_result is None:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.current_result.output_path)))

    def open_result_folder(self) -> None:
        """Open the folder containing the generated PDF."""

        if self.current_result is None:
            return
        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(self.current_result.output_path.parent))
        )

    def show_upload(self) -> None:
        """Return to the upload/options screen."""

        self.stack.setCurrentWidget(self.upload_panel)

    def reset_flow(self) -> None:
        """Reset the app to its initial state."""

        self.current_file_info = None
        self.current_analysis = None
        self.current_result = None
        self.upload_panel.clear_state()
        self.stack.setCurrentWidget(self.upload_panel)

    def _handle_analysis_complete(self, analysis: DocumentAnalysis) -> None:
        self._close_progress()
        self.current_analysis = analysis

        if analysis.warnings:
            QMessageBox.warning(self, 'Document warning', '\n\n'.join(analysis.warnings))

        if not analysis.matches:
            QMessageBox.information(
                self,
                'No matches found',
                'No matches were found for the selected criteria. '
                'No output file has been created.',
            )
            return

        self.review_panel.load_analysis(analysis)
        self.stack.setCurrentWidget(self.review_panel)

    def _handle_apply_complete(self, result: RedactionResult) -> None:
        self._close_progress()
        self.current_result = result
        self.result_panel.set_result(result)
        self.stack.setCurrentWidget(self.result_panel)

    def _handle_worker_failure(self, message: str) -> None:
        self._close_progress()
        self._show_error(message)

    def _show_progress(self, message: str) -> None:
        self.progress_dialog = BusyProgressDialog(message, self)
        self.progress_dialog.show()

    def _close_progress(self) -> None:
        if self.progress_dialog is not None:
            self.progress_dialog.close()
            self.progress_dialog.deleteLater()
            self.progress_dialog = None

    def _show_error(self, message: str) -> None:
        QMessageBox.critical(self, 'Tax PDF Redactor', message)

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            '''
            QMainWindow {
                background: #f5f1e8;
            }
            QLabel#screenTitle {
                color: #1d3557;
                font-size: 28px;
                font-weight: 700;
            }
            QLabel#sectionTitle {
                color: #254441;
                font-size: 16px;
                font-weight: 600;
            }
            QLabel#privacyNote {
                color: #4f6d7a;
                font-size: 14px;
            }
            QFrame#dropArea {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #fffaf0,
                    stop: 1 #f4d58d
                );
                border: 2px dashed #3a506b;
                border-radius: 18px;
            }
            QLabel#dropAreaTitle {
                color: #0b132b;
                font-size: 22px;
                font-weight: 700;
            }
            QPushButton {
                background: #faf3dd;
                border: 1px solid #a37a74;
                border-radius: 10px;
                color: #1f2933;
                min-height: 38px;
                padding: 0 16px;
            }
            QPushButton:hover {
                background: #ffe8b6;
            }
            QPushButton#primaryButton {
                background: #254441;
                border-color: #254441;
                color: #ffffff;
                font-weight: 600;
            }
            QPushButton#primaryButton:hover {
                background: #34675c;
            }
            QPlainTextEdit, QTreeWidget {
                background: #fffdf8;
                border: 1px solid #d9c6a5;
                border-radius: 10px;
                padding: 8px;
            }
            QCheckBox {
                color: #1f2933;
                spacing: 8px;
            }
            '''
        )
