"""Background workers for analysis and redaction jobs."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal

from app.core.models import RedactionMatch
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
