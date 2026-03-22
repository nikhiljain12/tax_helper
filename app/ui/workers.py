"""Background workers for analysis and redaction jobs."""

from __future__ import annotations

import dataclasses
from collections import Counter
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal

from app.core.models import BatchFileItem, BatchFileResult, BatchFileStatus, RedactionMatch, RedactionRequest
from app.core.redaction_engine import RedactionEngine


class WorkerSignals(QObject):
    """Signals emitted by a worker."""

    completed = Signal(object)
    failed = Signal(str)


class AnalyzeWorker(QRunnable):
    """Analyze a document in a background thread."""

    def __init__(self, engine: RedactionEngine, request) -> None:
        super().__init__()
        self.engine = engine
        self.request = request
        self.signals = WorkerSignals()

    def run(self) -> None:
        try:
            result = self.engine.analyze(self.request)
        except Exception as exc:  # pragma: no cover - Qt callback path
            self.signals.failed.emit(str(exc))
            return

        self.signals.completed.emit(result)


class ApplyWorker(QRunnable):
    """Apply selected redactions in a background thread."""

    def __init__(
        self,
        engine: RedactionEngine,
        input_path: Path,
        matches: list[RedactionMatch],
        selected_match_ids: set[str],
        output_path: Path,
    ) -> None:
        super().__init__()
        self.engine = engine
        self.input_path = input_path
        self.matches = matches
        self.selected_match_ids = selected_match_ids
        self.output_path = output_path
        self.signals = WorkerSignals()

    def run(self) -> None:
        try:
            result = self.engine.apply(
                input_path=self.input_path,
                matches=self.matches,
                selected_match_ids=self.selected_match_ids,
                output_path=self.output_path,
            )
        except Exception as exc:  # pragma: no cover - Qt callback path
            self.signals.failed.emit(str(exc))
            return

        self.signals.completed.emit(result)


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
