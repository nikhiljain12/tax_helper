"""Review screen for matches found during analysis."""

from __future__ import annotations

from collections import defaultdict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.models import DocumentAnalysis, RedactionMatch


def _category_label(raw_value: str) -> str:
    return {
        'name': 'Names',
        'address': 'Addresses',
        'tin': 'TIN / SSN / EIN',
        'phone': 'Phone',
        'email': 'Email',
        'custom': 'Custom text',
    }.get(raw_value, raw_value.title())


class ReviewPanel(QWidget):
    """Review and selection screen before saving the redacted PDF."""

    def __init__(self) -> None:
        super().__init__()

        self._matches: list[RedactionMatch] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)

        title = QLabel('Review Matches')
        title.setObjectName('screenTitle')

        self.summary_label = QLabel('No analysis loaded')
        self.summary_label.setWordWrap(True)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(['Match', 'Page', 'Occurrences', 'Context'])
        self.tree.setRootIsDecorated(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setUniformRowHeights(False)

        action_row = QHBoxLayout()
        action_row.setSpacing(12)

        self.select_all_button = QPushButton('Select All')
        self.deselect_all_button = QPushButton('Deselect All')
        self.back_button = QPushButton('Back')
        self.save_button = QPushButton('Redact & Save')
        self.save_button.setObjectName('primaryButton')

        self.select_all_button.clicked.connect(self.select_all)
        self.deselect_all_button.clicked.connect(self.deselect_all)

        action_row.addWidget(self.select_all_button)
        action_row.addWidget(self.deselect_all_button)
        action_row.addStretch(1)
        action_row.addWidget(self.back_button)
        action_row.addWidget(self.save_button)

        layout.addWidget(title)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.tree, 1)
        layout.addLayout(action_row)

    def load_analysis(self, analysis: DocumentAnalysis) -> None:
        """Populate the checklist with grouped matches."""

        self._matches = analysis.matches
        self.tree.clear()

        groups: dict[str, list[RedactionMatch]] = defaultdict(list)
        for match in analysis.matches:
            groups[match.category.value].append(match)

        categories_found = ', '.join(
            _category_label(category) for category in sorted(groups)
        ) or 'None'
        self.summary_label.setText(
            f'{analysis.page_count} page(s) scanned. '
            f'{len(analysis.matches)} reviewable match(es) found across: {categories_found}.'
        )

        for category in sorted(groups):
            category_matches = groups[category]
            parent = QTreeWidgetItem(
                [f'{_category_label(category)} ({len(category_matches)})', '', '', '']
            )
            parent.setFlags(
                parent.flags()
                | Qt.ItemIsUserCheckable
                | Qt.ItemIsAutoTristate
            )
            parent.setCheckState(0, Qt.Checked)
            self.tree.addTopLevelItem(parent)

            for match in category_matches:
                child = QTreeWidgetItem(
                    [
                        match.text,
                        str(match.page_number),
                        str(match.occurrence_count),
                        match.context or '',
                    ]
                )
                child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
                child.setCheckState(0, Qt.Checked)
                child.setData(0, Qt.UserRole, match.match_id)
                parent.addChild(child)

            parent.setExpanded(True)

        for column in range(self.tree.columnCount()):
            self.tree.resizeColumnToContents(column)

    def selected_match_ids(self) -> set[str]:
        """Return the IDs of all checked redactions."""

        selected: set[str] = set()

        for index in range(self.tree.topLevelItemCount()):
            parent = self.tree.topLevelItem(index)
            for child_index in range(parent.childCount()):
                child = parent.child(child_index)
                if child.checkState(0) == Qt.Checked:
                    selected.add(child.data(0, Qt.UserRole))

        return selected

    def select_all(self) -> None:
        """Check every match row."""

        self._set_all_children(Qt.Checked)

    def deselect_all(self) -> None:
        """Uncheck every match row."""

        self._set_all_children(Qt.Unchecked)

    def _set_all_children(self, state: Qt.CheckState) -> None:
        for index in range(self.tree.topLevelItemCount()):
            parent = self.tree.topLevelItem(index)
            parent.setCheckState(0, state)
