# Batch Folder Redaction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a batch folder redaction mode to the Tax PDF Redactor desktop app — scan a folder recursively, redact all PDFs automatically using existing rules, and display a per-file summary with per-category match counts.

**Architecture:** A new `FolderScanService` handles recursive PDF discovery and output-path mirroring. A new `BatchFolderWorker` (QRunnable) processes files sequentially in a background thread, calling the existing `RedactionEngine` without modification. The `UploadPanel` gains a mode toggle; a new `BatchResultPanel` is added to `MainWindow`'s `QStackedWidget`.

**Tech Stack:** Python 3.12, PySide6, PyMuPDF (fitz), `dataclasses`, `pathlib.Path`, `collections.Counter`

**Spec:** `docs/superpowers/specs/2026-03-22-batch-folder-redaction-design.md`

---

## File Structure

**New files:**

| File | Responsibility |
|---|---|
| `app/services/folder_scan_service.py` | Recursive PDF discovery, output-path mirroring |
| `app/ui/batch_progress_dialog.py` | Deterministic progress bar during batch run |
| `app/ui/batch_result_panel.py` | Post-run summary screen with file-by-file table |
| `tests/test_folder_scan_service.py` | Unit tests for `FolderScanService` |
| `tests/test_batch_worker.py` | Unit tests for `BatchFolderWorker` (mocked engine) |

**Modified files:**

| File | Change |
|---|---|
| `app/core/models.py` | Add `BatchFileItem`, `BatchFileStatus`, `BatchFileResult` |
| `app/ui/workers.py` | Add `BatchProgressSignals`, `BatchFolderWorker` |
| `app/ui/upload_panel.py` | Add mode toggle, folder picker rows, `batch_requested` signal |
| `app/ui/main_window.py` | Wire batch flow, add `BatchResultPanel` to stack, "Open Folder..." menu |

---

## Task 1: Add Batch Models

**Files:**
- Modify: `app/core/models.py`
- Create: `tests/test_batch_models.py`

The existing models are frozen dataclasses in `app/core/models.py`. Add the three new batch models after `RedactionResult`. You will need to add `from dataclasses import field` to the existing imports.

- [ ] **Step 1: Write the failing test**

Create `tests/test_batch_models.py`:

```python
"""Tests for batch redaction models."""

from __future__ import annotations

import unittest
from pathlib import Path

from app.core.models import BatchFileResult, BatchFileStatus, RedactionCategory


class TestBatchFileResult(unittest.TestCase):

    def test_total_matches_sums_all_categories(self) -> None:
        result = BatchFileResult(
            input_path=Path('a.pdf'),
            output_path=Path('a_redacted.pdf'),
            status=BatchFileStatus.REDACTED,
            match_counts={RedactionCategory.TIN: 3, RedactionCategory.NAME: 1},
        )
        self.assertEqual(4, result.total_matches)

    def test_total_matches_empty_is_zero(self) -> None:
        result = BatchFileResult(
            input_path=Path('a.pdf'),
            output_path=Path('a_redacted.pdf'),
            status=BatchFileStatus.NO_MATCHES,
        )
        self.assertEqual(0, result.total_matches)

    def test_default_match_counts_is_empty_dict(self) -> None:
        result = BatchFileResult(
            input_path=Path('a.pdf'),
            output_path=Path('a_redacted.pdf'),
            status=BatchFileStatus.ERROR,
            error_message='something went wrong',
        )
        self.assertEqual({}, result.match_counts)
        self.assertEqual('something went wrong', result.error_message)


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/nikhiljain/code/tax_helper && source .venv/bin/activate && python -m pytest tests/test_batch_models.py -v
```

Expected: `ImportError` — `BatchFileResult`, `BatchFileStatus` not yet defined.

- [ ] **Step 3: Add the models to `app/core/models.py`**

Add `from dataclasses import dataclass, field` (replace the existing `from dataclasses import dataclass` import). Then add these three classes after the `RedactionResult` dataclass:

```python
class BatchFileStatus(str, Enum):
    """Outcome status for a single file in a batch run."""

    REDACTED = 'redacted'
    NO_MATCHES = 'no_matches'
    ERROR = 'error'


@dataclass
class BatchFileItem:
    """A planned input→output file pair for a batch run."""

    input_path: Path
    output_path: Path


@dataclass
class BatchFileResult:
    """Outcome for a single file processed during a batch run."""

    input_path: Path
    output_path: Path
    status: BatchFileStatus
    match_counts: dict[RedactionCategory, int] = field(default_factory=dict)
    error_message: str | None = None

    @property
    def total_matches(self) -> int:
        return sum(self.match_counts.values())
```

Note: `BatchFileItem` and `BatchFileResult` are **not** frozen (unlike the existing models) because they are mutable results, not inputs to the engine.

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_batch_models.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/core/models.py tests/test_batch_models.py
git commit -m "feat: add BatchFileItem, BatchFileStatus, BatchFileResult models"
```

---

## Task 2: FolderScanService

**Files:**
- Create: `app/services/folder_scan_service.py`
- Create: `tests/test_folder_scan_service.py`

This service has no Qt dependency — pure Python. It walks a directory with `Path.rglob("*.pdf")`, filters out files whose stem contains `"redacted"` (case-insensitive), and computes mirrored output paths.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_folder_scan_service.py`:

```python
"""Tests for FolderScanService."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.services.folder_scan_service import FolderScanService


class TestFolderScanService(unittest.TestCase):

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.input_folder = root / 'input'
        self.output_folder = root / 'output'
        self.input_folder.mkdir()
        self.service = FolderScanService()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _touch(self, relative: str) -> Path:
        """Create an empty file at input_folder/relative."""
        path = self.input_folder / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        return path

    def test_finds_pdf_in_root(self) -> None:
        self._touch('file0.pdf')
        items = self.service.scan(self.input_folder, self.output_folder)
        self.assertEqual(1, len(items))
        self.assertEqual(self.input_folder / 'file0.pdf', items[0].input_path)
        self.assertEqual(self.output_folder / 'file0_redacted.pdf', items[0].output_path)

    def test_finds_pdf_in_subfolder(self) -> None:
        self._touch('sub_a/file1.pdf')
        items = self.service.scan(self.input_folder, self.output_folder)
        self.assertEqual(1, len(items))
        self.assertEqual(self.output_folder / 'sub_a' / 'file1_redacted.pdf', items[0].output_path)

    def test_finds_pdf_in_deeply_nested_subfolder(self) -> None:
        self._touch('sub_b/sub_c/file2.pdf')
        items = self.service.scan(self.input_folder, self.output_folder)
        self.assertEqual(1, len(items))
        self.assertEqual(
            self.output_folder / 'sub_b' / 'sub_c' / 'file2_redacted.pdf',
            items[0].output_path,
        )

    def test_skips_files_with_redacted_in_stem_lowercase(self) -> None:
        self._touch('file1.pdf')
        self._touch('file1_redacted.pdf')
        items = self.service.scan(self.input_folder, self.output_folder)
        self.assertEqual(1, len(items))
        self.assertEqual(self.input_folder / 'file1.pdf', items[0].input_path)

    def test_skips_files_with_redacted_in_stem_uppercase(self) -> None:
        self._touch('file2_REDACTED.pdf')
        items = self.service.scan(self.input_folder, self.output_folder)
        self.assertEqual([], items)

    def test_ignores_non_pdf_files(self) -> None:
        self._touch('file1.pdf')
        (self.input_folder / 'notes.txt').touch()
        (self.input_folder / 'data.csv').touch()
        items = self.service.scan(self.input_folder, self.output_folder)
        self.assertEqual(1, len(items))

    def test_empty_folder_returns_empty_list(self) -> None:
        items = self.service.scan(self.input_folder, self.output_folder)
        self.assertEqual([], items)

    def test_all_filtered_returns_empty_list(self) -> None:
        self._touch('file1_redacted.pdf')
        self._touch('file2_redacted.pdf')
        items = self.service.scan(self.input_folder, self.output_folder)
        self.assertEqual([], items)

    def test_preserves_subfolder_structure_across_multiple_folders(self) -> None:
        self._touch('file0.pdf')
        self._touch('sub_a/file1.pdf')
        self._touch('sub_a/file2_redacted.pdf')   # should be skipped
        self._touch('sub_b/sub_c/file3.pdf')

        items = self.service.scan(self.input_folder, self.output_folder)
        output_paths = {item.output_path for item in items}

        self.assertEqual(3, len(items))
        self.assertIn(self.output_folder / 'file0_redacted.pdf', output_paths)
        self.assertIn(self.output_folder / 'sub_a' / 'file1_redacted.pdf', output_paths)
        self.assertIn(self.output_folder / 'sub_b' / 'sub_c' / 'file3_redacted.pdf', output_paths)

    def test_results_are_sorted_by_input_path(self) -> None:
        self._touch('b.pdf')
        self._touch('a.pdf')
        self._touch('sub/c.pdf')
        items = self.service.scan(self.input_folder, self.output_folder)
        paths = [item.input_path for item in items]
        self.assertEqual(sorted(paths), paths)


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_folder_scan_service.py -v
```

Expected: `ModuleNotFoundError` — `folder_scan_service` not yet created.

- [ ] **Step 3: Implement `FolderScanService`**

Create `app/services/folder_scan_service.py`:

```python
"""Recursive PDF discovery and output-path mirroring for batch redaction."""

from __future__ import annotations

from pathlib import Path

from app.core.models import BatchFileItem


class FolderScanService:
    """Scans a folder recursively and builds a list of input→output file pairs."""

    def scan(self, input_folder: Path, output_folder: Path) -> list[BatchFileItem]:
        """Return sorted BatchFileItems for all non-redacted PDFs under input_folder."""

        items: list[BatchFileItem] = []
        for pdf_path in sorted(input_folder.rglob('*.pdf')):
            if 'redacted' in pdf_path.stem.lower():
                continue
            relative = pdf_path.relative_to(input_folder)
            output_path = output_folder / relative.parent / f'{pdf_path.stem}_redacted.pdf'
            items.append(BatchFileItem(input_path=pdf_path, output_path=output_path))
        return items
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_folder_scan_service.py -v
```

Expected: All 10 tests PASS.

- [ ] **Step 5: Run full test suite to confirm no regressions**

```bash
python -m pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add app/services/folder_scan_service.py tests/test_folder_scan_service.py
git commit -m "feat: add FolderScanService for recursive PDF discovery"
```

---

## Task 3: BatchFolderWorker

**Files:**
- Modify: `app/ui/workers.py`
- Create: `tests/test_batch_worker.py`

The worker calls `engine.analyze()` per file, then `engine.apply()` if matches are found. It uses `dataclasses.replace()` to swap `input_path` in the request template without modifying the original. Match counts are computed via `Counter`.

Tests call `worker.run()` directly (no thread pool needed) and collect results via the `all_done` signal. PySide6 signals emit synchronously in the same thread, but a `QCoreApplication` instance must exist.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_batch_worker.py`:

```python
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
    ExactValueRule,
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


def _make_match(category: RedactionCategory = RedactionCategory.TIN) -> RedactionMatch:
    return RedactionMatch(
        match_id='id1',
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
            _make_match(RedactionCategory.TIN),
            _make_match(RedactionCategory.TIN),
            _make_match(RedactionCategory.NAME),
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
        selected_ids = call_kwargs.kwargs.get('selected_match_ids') or call_kwargs[1].get('selected_match_ids') or call_kwargs[0][2]
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_batch_worker.py -v
```

Expected: `ImportError` — `BatchFolderWorker` not yet defined.

- [ ] **Step 3: Add `BatchFolderWorker` to `app/ui/workers.py`**

Add these imports at the top of `app/ui/workers.py` (alongside existing ones):

```python
import dataclasses
from collections import Counter
from app.core.models import BatchFileItem, BatchFileResult, BatchFileStatus, RedactionRequest
```

Then add these two classes at the bottom of `app/ui/workers.py`:

```python
class BatchProgressSignals(QObject):
    """Signals emitted by BatchFolderWorker."""

    file_started = Signal(int, int, str)  # (current_index, total, relative_filename)
    file_done = Signal(object)            # BatchFileResult
    all_done = Signal(object)             # list[BatchFileResult]
    failed = Signal(str)                  # fatal pre-loop error


class BatchFolderWorker(QRunnable):
    """Process a list of PDF files sequentially in a background thread."""

    def __init__(
        self,
        engine: RedactionEngine,
        items: list[BatchFileItem],
        request_template: RedactionRequest,
        input_folder: Path,
    ) -> None:
        super().__init__()
        self.engine = engine
        self.items = items
        self.request_template = request_template
        self.input_folder = input_folder
        self.signals = BatchProgressSignals()

    def run(self) -> None:
        if not self.items:
            self.signals.failed.emit('No PDF files found in the selected folder.')
            return

        total = len(self.items)
        results: list[BatchFileResult] = []

        for i, item in enumerate(self.items):
            display_name = str(item.input_path.relative_to(self.input_folder))
            self.signals.file_started.emit(i + 1, total, display_name)

            try:
                per_file_request = dataclasses.replace(
                    self.request_template, input_path=item.input_path
                )
                analysis = self.engine.analyze(per_file_request)
            except Exception as exc:
                result = BatchFileResult(
                    input_path=item.input_path,
                    output_path=item.output_path,
                    status=BatchFileStatus.ERROR,
                    error_message=str(exc),
                )
                results.append(result)
                self.signals.file_done.emit(result)
                continue

            if not analysis.matches:
                result = BatchFileResult(
                    input_path=item.input_path,
                    output_path=item.output_path,
                    status=BatchFileStatus.NO_MATCHES,
                )
                results.append(result)
                self.signals.file_done.emit(result)
                continue

            try:
                all_match_ids = {m.match_id for m in analysis.matches}
                self.engine.apply(
                    input_path=item.input_path,
                    matches=analysis.matches,
                    selected_match_ids=all_match_ids,
                    output_path=item.output_path,
                )
                match_counts = dict(Counter(m.category for m in analysis.matches))
                result = BatchFileResult(
                    input_path=item.input_path,
                    output_path=item.output_path,
                    status=BatchFileStatus.REDACTED,
                    match_counts=match_counts,
                )
            except Exception as exc:
                result = BatchFileResult(
                    input_path=item.input_path,
                    output_path=item.output_path,
                    status=BatchFileStatus.ERROR,
                    error_message=str(exc),
                )

            results.append(result)
            self.signals.file_done.emit(result)

        self.signals.all_done.emit(results)
```

Note: `Path` is already imported in `workers.py` — confirm this before adding a duplicate import.

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_batch_worker.py -v
```

Expected: All 8 tests PASS.

- [ ] **Step 5: Run full test suite**

```bash
python -m pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add app/ui/workers.py tests/test_batch_worker.py
git commit -m "feat: add BatchFolderWorker for sequential batch PDF redaction"
```

---

## Task 4: BatchProgressDialog

**Files:**
- Create: `app/ui/batch_progress_dialog.py`

No unit tests — this is a pure Qt widget. Verified manually in Task 7.

- [ ] **Step 1: Create `app/ui/batch_progress_dialog.py`**

```python
"""Progress dialog for batch folder redaction."""

from __future__ import annotations

from pathlib import Path

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
```

- [ ] **Step 2: Verify the import works**

```bash
python -c "from app.ui.batch_progress_dialog import BatchProgressDialog; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/ui/batch_progress_dialog.py
git commit -m "feat: add BatchProgressDialog for batch run progress display"
```

---

## Task 5: BatchResultPanel

**Files:**
- Create: `app/ui/batch_result_panel.py`

No unit tests — pure Qt widget. Verified manually in Task 7. The panel uses a `QTreeWidget` so error rows can have child items with the full message. File paths are displayed relative to `input_folder`.

- [ ] **Step 1: Create `app/ui/batch_result_panel.py`**

```python
"""Post-run summary screen for batch folder redaction."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
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
```

- [ ] **Step 2: Verify the import works**

```bash
python -c "from app.ui.batch_result_panel import BatchResultPanel; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/ui/batch_result_panel.py
git commit -m "feat: add BatchResultPanel for batch run summary display"
```

---

## Task 6: UploadPanel Mode Toggle

**Files:**
- Modify: `app/ui/upload_panel.py`

Add a mode toggle (two exclusive `QPushButton`s via `QButtonGroup`) and a batch folder picker section. In Single File mode the existing drop zone is shown; in Batch Folder mode it is hidden and replaced by folder picker rows. The primary action button label and emitted signal change based on the active mode.

No unit tests — pure Qt widget. Verified manually in Task 7.

- [ ] **Step 1: Read the current `upload_panel.py` in full before editing**

Confirm the current layout order: title → privacy_note → drop_area → file_controls → form_title → form_layout → detect_title → detect_layout → case_sensitive_checkbox → stretch → find_matches_button.

- [ ] **Step 2: Update imports in `app/ui/upload_panel.py`**

Add to the existing PySide6 imports:
- `QButtonGroup` from `PySide6.QtWidgets`
- `QFileDialog` from `PySide6.QtWidgets`
- `QLineEdit` from `PySide6.QtWidgets`

- [ ] **Step 3: Add `batch_requested` signal and mode toggle to `UploadPanel.__init__`**

Replace the existing `UploadPanel.__init__` with the updated version below. The key changes are:
1. Add `batch_requested = Signal(Path, Path)` class-level signal.
2. Insert a mode toggle row (two checkable QPushButtons in a QButtonGroup) between the privacy note and the drop area.
3. Add a `self._batch_folder_widget` (hidden by default) containing input folder row and output folder row.
4. Rename `self.find_matches_button` → keep the name, but wire it to `_on_primary_action`.
5. Add `_on_primary_action`, `_on_mode_changed`, `choose_input_folder`, `choose_output_folder` methods.

```python
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
```

- [ ] **Step 4: Add the new methods to `UploadPanel`**

Add these methods to the `UploadPanel` class:

```python
    def _on_mode_changed(self) -> None:
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
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, 'Tax PDF Redactor', 'Please select an input folder.')
            return

        input_folder = Path(input_path_str)
        if not input_folder.is_dir():
            from PySide6.QtWidgets import QMessageBox
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
```

- [ ] **Step 5: Update `clear_state` to reset batch fields too**

In the existing `clear_state` method, add after the checkbox resets:

```python
        self._input_folder_edit.clear()
        self._output_folder_edit.clear()
        self._single_file_btn.setChecked(True)
        self._on_mode_changed()
```

- [ ] **Step 6: Verify the import works**

```bash
python -c "from app.ui.upload_panel import UploadPanel; print('OK')"
```

Expected: `OK`

- [ ] **Step 7: Run full test suite**

```bash
python -m pytest tests/ -v
```

Expected: All tests PASS (no regressions — `upload_panel` has no unit tests).

- [ ] **Step 8: Commit**

```bash
git add app/ui/upload_panel.py
git commit -m "feat: add mode toggle and batch folder picker to UploadPanel"
```

---

## Task 7: MainWindow Wiring

**Files:**
- Modify: `app/ui/main_window.py`

Connect everything together: add `BatchResultPanel` to the stack, add "Open Folder..." to the File menu, wire `upload_panel.batch_requested` → `start_batch()`, and handle batch worker signals.

- [ ] **Step 1: Add new imports to `app/ui/main_window.py`**

Add to the existing imports:

```python
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from app.core.models import BatchFileResult
from app.services.folder_scan_service import FolderScanService
from app.ui.batch_progress_dialog import BatchProgressDialog
from app.ui.batch_result_panel import BatchResultPanel
from app.ui.workers import BatchFolderWorker
```

Note: `QUrl` and `QDesktopServices` are already imported — check before adding duplicates.

- [ ] **Step 2: Update `MainWindow.__init__`**

In `__init__`, after `self.result_panel = ResultPanel()` and before `self.stack.addWidget(...)`, add:

```python
        self.batch_result_panel = BatchResultPanel()
        self.folder_scan_service = FolderScanService()
        self._batch_input_folder: Path | None = None
```

After `self.stack.addWidget(self.result_panel)`, add:

```python
        self.stack.addWidget(self.batch_result_panel)
```

After the existing signal connections, add:

```python
        self.upload_panel.batch_requested.connect(self.start_batch)
        self.batch_result_panel.reset_button.clicked.connect(self.reset_flow)
        self.batch_result_panel.open_folder_button.clicked.connect(self.open_batch_output_folder)
```

- [ ] **Step 3: Add "Open Folder..." to the File menu**

In `_build_menu_bar`, after `open_action` is created and added to `file_menu`, and before `self._recent_menu` is added, insert the new action using `insertAction` so it appears between "Open..." and "Open Recent":

```python
        open_folder_action = QAction('Open &Folder...', self)
        open_folder_action.setShortcut('Ctrl+Shift+O')
        open_folder_action.triggered.connect(self.choose_folder)
        # insertAction places it before the "Open Recent" submenu entry
        file_menu.insertAction(self._recent_menu.menuAction(), open_folder_action)
```

Note: `self._recent_menu` must be created before this line. In the current `_build_menu_bar`, `self._recent_menu` is built right after `open_action`. Move the `self._recent_menu` creation to before this insertion, or create `open_folder_action` after `self._recent_menu` is assigned.

- [ ] **Step 4: Add `choose_folder` method**

```python
    def choose_folder(self) -> None:
        """Open the native folder picker and switch UploadPanel to batch mode."""
        folder = QFileDialog.getExistingDirectory(
            self,
            'Choose Input Folder',
            self.app_settings.last_open_dir(),
        )
        if folder:
            self.upload_panel._batch_folder_btn.setChecked(True)
            self.upload_panel._on_mode_changed()
            self.upload_panel._input_folder_edit.setText(folder)
            self.stack.setCurrentWidget(self.upload_panel)
```

- [ ] **Step 5: Add `start_batch` method**

```python
    def start_batch(self, input_folder: Path, output_folder: Path) -> None:
        """Scan the folder and launch a batch redaction worker."""
        options = self.upload_panel.collect_options()

        try:
            request_template = self.workflow.build_request(
                input_path=input_folder,  # placeholder; replaced per file in worker
                names=self.workflow.parse_multivalue_text(options['names']),
                addresses=self.workflow.parse_multivalue_text(options['addresses']),
                tins=self.workflow.parse_multivalue_text(options['tins']),
                custom_strings=self.workflow.parse_multivalue_text(options['custom_strings']),
                detect_tin=bool(options['detect_tin']),
                detect_phone=bool(options['detect_phone']),
                detect_email=bool(options['detect_email']),
                case_sensitive=bool(options['case_sensitive']),
            )
        except ValueError as exc:
            self._show_error(str(exc))
            return

        items = self.folder_scan_service.scan(input_folder, output_folder)
        if not items:
            self._show_error(
                'No PDF files found in the selected folder.\n'
                '(Files already named "*redacted*" are skipped.)'
            )
            return

        self._batch_input_folder = input_folder

        dialog = BatchProgressDialog(total=len(items), parent=self)
        worker = BatchFolderWorker(
            engine=self.engine,
            items=items,
            request_template=request_template,
            input_folder=input_folder,
        )
        worker.signals.file_started.connect(dialog.update_progress)
        worker.signals.all_done.connect(
            lambda results: self._handle_batch_complete(results, input_folder, output_folder, dialog)
        )
        worker.signals.failed.connect(
            lambda msg: (dialog.close(), dialog.deleteLater(), self._show_error(msg))
        )
        dialog.show()
        self.thread_pool.start(worker)
```

- [ ] **Step 6: Add `_handle_batch_complete` method**

```python
    def _handle_batch_complete(
        self,
        results: list[BatchFileResult],
        input_folder: Path,
        output_folder: Path,
        dialog: BatchProgressDialog,
    ) -> None:
        dialog.close()
        dialog.deleteLater()
        self.batch_result_panel.load_results(results, input_folder, output_folder)
        self.stack.setCurrentWidget(self.batch_result_panel)
```

- [ ] **Step 7: Add `open_batch_output_folder` method**

```python
    def open_batch_output_folder(self) -> None:
        """Open the batch output folder in Finder/Explorer."""
        folder = self.batch_result_panel.output_folder()
        if folder and folder.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
```

- [ ] **Step 8: Verify the import works**

```bash
python -c "from app.ui.main_window import MainWindow; print('OK')"
```

Expected: `OK`

- [ ] **Step 9: Run full test suite**

```bash
python -m pytest tests/ -v
```

Expected: All tests PASS.

- [ ] **Step 10: Launch the app and manually verify the batch flow**

```bash
python desktop_main.py
```

Manual QA checklist:
- [ ] App launches. Upload screen shows "Single File" and "Batch Folder" toggle buttons.
- [ ] Clicking "Batch Folder" hides the drop zone and shows Input/Output folder rows; button label changes to "Redact Folder".
- [ ] Clicking "Single File" restores the drop zone; button label reverts to "Find Matches".
- [ ] "Open Folder..." in the File menu opens a folder picker and switches to Batch Folder mode.
- [ ] Clicking "Redact Folder" with no input folder shows a warning dialog.
- [ ] Clicking "Redact Folder" with no redaction options configured shows the "No criteria" error.
- [ ] Select a folder with 2+ PDFs and valid options → progress dialog shows per-file progress.
- [ ] After completion → BatchResultPanel shows correct file count, statuses, and match counts.
- [ ] Files named `*_redacted.pdf` in the input folder are skipped (do not appear in results).
- [ ] A password-protected or corrupt PDF appears as "Error" in the results table; others complete.
- [ ] Expanding an error row shows the full error message.
- [ ] "Open Output Folder" opens the output folder in Finder.
- [ ] "Redact Another Folder" returns to the upload screen in a clean state.
- [ ] Single-file flow (Find Matches → Review → Save) still works as before.

- [ ] **Step 11: Commit**

```bash
git add app/ui/main_window.py
git commit -m "feat: wire batch folder redaction flow into MainWindow"
```

---

## Done

All tasks complete. The batch folder redaction feature is fully implemented:
- `FolderScanService` recursively finds PDFs and mirrors output paths
- `BatchFolderWorker` processes files sequentially, skipping and logging errors
- `BatchProgressDialog` shows per-file progress
- `BatchResultPanel` shows a file-by-file summary with per-category match counts and expandable error details
- `UploadPanel` has a mode toggle; batch mode shows folder pickers
- `MainWindow` wires everything together with "Open Folder..." in the File menu
