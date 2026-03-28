"""Post-run summary screen for batch folder redaction."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.models import BatchFileResult, BatchFileStatus


class BatchResultPanel(QWidget):
    """Screen showing per-file results after a batch redaction run."""

    def __init__(self) -> None:
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)

        self._title = QLabel('Batch Complete')
        self._title.setObjectName('screenTitle')

        self._summary_label = QLabel()
        self._summary_label.setObjectName('privacyNote')

        self._tree = QTreeWidget()
        self._tree.setColumnCount(4)
        self._tree.setHeaderLabels(['File', 'Status', 'Matches', 'Error'])
        self._tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._tree.setAlternatingRowColors(True)

        button_row = QHBoxLayout()
        self.open_folder_button = QPushButton('Open Output Folder')
        self.reset_button = QPushButton('Redact Another Folder')
        self.reset_button.setObjectName('primaryButton')
        button_row.addWidget(self.open_folder_button)
        button_row.addStretch(1)
        button_row.addWidget(self.reset_button)

        layout.addWidget(self._title)
        layout.addWidget(self._summary_label)
        layout.addWidget(self._tree)
        layout.addLayout(button_row)

        self._output_folder: Path | None = None

    def load_results(
        self,
        results: list[BatchFileResult],
        input_folder: Path,
        output_folder: Path,
    ) -> None:
        """Populate the summary table from a completed batch run."""
        self._output_folder = output_folder
        self._tree.clear()

        redacted = sum(1 for r in results if r.status == BatchFileStatus.REDACTED)
        no_match = sum(1 for r in results if r.status == BatchFileStatus.NO_MATCHES)
        errors = sum(1 for r in results if r.status == BatchFileStatus.ERROR)
        self._summary_label.setText(
            f'{len(results)} files  ·  {redacted} redacted  ·  '
            f'{no_match} no matches  ·  {errors} errors'
        )

        status_labels = {
            BatchFileStatus.REDACTED: 'Redacted',
            BatchFileStatus.NO_MATCHES: 'No matches',
            BatchFileStatus.ERROR: 'Error',
        }

        for result in results:
            try:
                display_path = str(result.input_path.relative_to(input_folder))
            except ValueError:
                display_path = result.input_path.name

            status_text = status_labels[result.status]

            if result.status == BatchFileStatus.REDACTED:
                matches_text = '  '.join(
                    f'{cat.value[:3].title()}:{count}'
                    for cat, count in sorted(
                        result.match_counts.items(), key=lambda x: x[0].value
                    )
                )
                tooltip = str(result.output_path)
            else:
                matches_text = ''
                tooltip = ''

            item = QTreeWidgetItem([display_path, status_text, matches_text, ''])
            if tooltip:
                item.setToolTip(0, tooltip)
                item.setToolTip(2, tooltip)

            if result.status == BatchFileStatus.ERROR and result.error_message:
                short_msg = result.error_message[:50]
                if len(result.error_message) > 50:
                    short_msg += '...'
                item.setText(3, f'\u25b6 {short_msg}')
                error_child = QTreeWidgetItem(['', '', '', result.error_message])
                item.addChild(error_child)

            self._tree.addTopLevelItem(item)

    def output_folder(self) -> Path | None:
        return self._output_folder
