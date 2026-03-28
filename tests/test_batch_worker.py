"""Tests for BatchFolderWorker."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from PySide6.QtCore import QCoreApplication

from app.core.models import (
    BatchFileItem,
    BatchFileStatus,
    DocumentAnalysis,
    RedactionCategory,
    RedactionMatch,
    RedactionRequest,
)
from app.ui.workers import BatchFolderWorker

# One QCoreApplication for the whole test module (required for QObject/signals).
_app = QCoreApplication.instance() or QCoreApplication(sys.argv[:1])


def _make_request() -> RedactionRequest:
    return RedactionRequest(
        input_path=Path('.'),
        exact_rules=[],
        pattern_rules=[],
    )


def _make_match(category: RedactionCategory = RedactionCategory.TIN, match_id: str = 'id1') -> RedactionMatch:
    return RedactionMatch(
        match_id=match_id,
        category=category,
        text='123-45-6789',
        page_number=1,
        rects=[(0.0, 0.0, 10.0, 10.0)],
        context=None,
        source_rule='exact:tin',
    )


def _run_worker(worker: BatchFolderWorker) -> list:
    """Run the worker synchronously and return the all_done results list."""
    collected: list = []
    worker.signals.all_done.connect(collected.append)
    worker.run()
    return collected[0] if collected else []


class TestBatchFolderWorker(unittest.TestCase):

    def test_redacted_file_returns_redacted_status_and_counts(self) -> None:
        input_folder = Path('/fake/input')
        item = BatchFileItem(
            input_path=input_folder / 'file.pdf',
            output_path=Path('/fake/output/file_redacted.pdf'),
        )
        match = _make_match(RedactionCategory.TIN)
        analysis = DocumentAnalysis(page_count=1, matches=[match], warnings=[])

        engine = MagicMock()
        engine.analyze.return_value = analysis
        engine.apply.return_value = MagicMock()

        worker = BatchFolderWorker(
            engine=engine,
            items=[item],
            request_template=_make_request(),
            input_folder=input_folder,
        )
        results = _run_worker(worker)

        self.assertEqual(1, len(results))
        self.assertEqual(BatchFileStatus.REDACTED, results[0].status)
        self.assertEqual({RedactionCategory.TIN: 1}, results[0].match_counts)
        self.assertIsNone(results[0].error_message)

    def test_multiple_match_categories_counted_correctly(self) -> None:
        input_folder = Path('/fake/input')
        item = BatchFileItem(
            input_path=input_folder / 'file.pdf',
            output_path=Path('/fake/output/file_redacted.pdf'),
        )
        matches = [
            _make_match(RedactionCategory.TIN, match_id='m1'),
            _make_match(RedactionCategory.TIN, match_id='m2'),
            _make_match(RedactionCategory.NAME, match_id='m3'),
        ]
        analysis = DocumentAnalysis(page_count=1, matches=matches, warnings=[])

        engine = MagicMock()
        engine.analyze.return_value = analysis
        engine.apply.return_value = MagicMock()

        worker = BatchFolderWorker(
            engine=engine,
            items=[item],
            request_template=_make_request(),
            input_folder=input_folder,
        )
        results = _run_worker(worker)

        self.assertEqual({RedactionCategory.TIN: 2, RedactionCategory.NAME: 1}, results[0].match_counts)
        self.assertEqual(3, results[0].total_matches)

    def test_no_matches_returns_no_matches_status_and_skips_apply(self) -> None:
        input_folder = Path('/fake/input')
        item = BatchFileItem(
            input_path=input_folder / 'file.pdf',
            output_path=Path('/fake/output/file_redacted.pdf'),
        )
        analysis = DocumentAnalysis(page_count=1, matches=[], warnings=[])

        engine = MagicMock()
        engine.analyze.return_value = analysis

        worker = BatchFolderWorker(
            engine=engine,
            items=[item],
            request_template=_make_request(),
            input_folder=input_folder,
        )
        results = _run_worker(worker)

        self.assertEqual(1, len(results))
        self.assertEqual(BatchFileStatus.NO_MATCHES, results[0].status)
        engine.apply.assert_not_called()

    def test_analyze_exception_returns_error_status(self) -> None:
        input_folder = Path('/fake/input')
        item = BatchFileItem(
            input_path=input_folder / 'bad.pdf',
            output_path=Path('/fake/output/bad_redacted.pdf'),
        )

        engine = MagicMock()
        engine.analyze.side_effect = ValueError('corrupted file')

        worker = BatchFolderWorker(
            engine=engine,
            items=[item],
            request_template=_make_request(),
            input_folder=input_folder,
        )
        results = _run_worker(worker)

        self.assertEqual(1, len(results))
        self.assertEqual(BatchFileStatus.ERROR, results[0].status)
        self.assertIn('corrupted file', results[0].error_message)

    def test_apply_exception_returns_error_status(self) -> None:
        input_folder = Path('/fake/input')
        item = BatchFileItem(
            input_path=input_folder / 'file.pdf',
            output_path=Path('/fake/output/file_redacted.pdf'),
        )
        analysis = DocumentAnalysis(page_count=1, matches=[_make_match()], warnings=[])

        engine = MagicMock()
        engine.analyze.return_value = analysis
        engine.apply.side_effect = IOError('disk full')

        worker = BatchFolderWorker(
            engine=engine,
            items=[item],
            request_template=_make_request(),
            input_folder=input_folder,
        )
        results = _run_worker(worker)

        self.assertEqual(1, len(results))
        self.assertEqual(BatchFileStatus.ERROR, results[0].status)
        self.assertIn('disk full', results[0].error_message)

    def test_processes_all_files_continuing_after_error(self) -> None:
        input_folder = Path('/fake/input')
        items = [
            BatchFileItem(input_folder / 'file1.pdf', Path('/fake/out/file1_redacted.pdf')),
            BatchFileItem(input_folder / 'file2.pdf', Path('/fake/out/file2_redacted.pdf')),
            BatchFileItem(input_folder / 'file3.pdf', Path('/fake/out/file3_redacted.pdf')),
        ]
        match = _make_match()
        good = DocumentAnalysis(page_count=1, matches=[match], warnings=[])
        empty = DocumentAnalysis(page_count=1, matches=[], warnings=[])

        engine = MagicMock()
        engine.analyze.side_effect = [good, ValueError('bad file'), empty]
        engine.apply.return_value = MagicMock()

        worker = BatchFolderWorker(
            engine=engine,
            items=items,
            request_template=_make_request(),
            input_folder=input_folder,
        )
        results = _run_worker(worker)

        self.assertEqual(3, len(results))
        self.assertEqual(BatchFileStatus.REDACTED, results[0].status)
        self.assertEqual(BatchFileStatus.ERROR, results[1].status)
        self.assertEqual(BatchFileStatus.NO_MATCHES, results[2].status)

    def test_apply_called_with_all_match_ids_selected(self) -> None:
        input_folder = Path('/fake/input')
        item = BatchFileItem(
            input_path=input_folder / 'file.pdf',
            output_path=Path('/fake/output/file_redacted.pdf'),
        )
        m1 = RedactionMatch('id1', RedactionCategory.TIN, '111', 1, [(0, 0, 1, 1)], None, 'x')
        m2 = RedactionMatch('id2', RedactionCategory.NAME, 'Jane', 1, [(0, 0, 1, 1)], None, 'x')
        analysis = DocumentAnalysis(page_count=1, matches=[m1, m2], warnings=[])

        engine = MagicMock()
        engine.analyze.return_value = analysis
        engine.apply.return_value = MagicMock()

        worker = BatchFolderWorker(
            engine=engine,
            items=[item],
            request_template=_make_request(),
            input_folder=input_folder,
        )
        _run_worker(worker)

        engine.apply.assert_called_once()
        call_kwargs = engine.apply.call_args
        selected_ids = call_kwargs.kwargs['selected_match_ids']
        self.assertEqual({'id1', 'id2'}, selected_ids)

    def test_file_started_signal_emits_relative_path(self) -> None:
        input_folder = Path('/fake/input')
        item = BatchFileItem(
            input_path=input_folder / 'sub' / 'file.pdf',
            output_path=Path('/fake/output/sub/file_redacted.pdf'),
        )
        analysis = DocumentAnalysis(page_count=1, matches=[], warnings=[])

        engine = MagicMock()
        engine.analyze.return_value = analysis

        started: list[tuple] = []
        worker = BatchFolderWorker(
            engine=engine,
            items=[item],
            request_template=_make_request(),
            input_folder=input_folder,
        )
        worker.signals.file_started.connect(lambda i, t, name: started.append((i, t, name)))
        worker.run()

        self.assertEqual(1, len(started))
        self.assertEqual(1, started[0][0])   # current_index
        self.assertEqual(1, started[0][1])   # total
        self.assertIn('sub', started[0][2])  # relative path contains subfolder


if __name__ == '__main__':
    unittest.main()
