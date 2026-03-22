"""Typed models for PDF redaction workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class RedactionCategory(str, Enum):
    """Supported redaction categories."""

    NAME = 'name'
    ADDRESS = 'address'
    TIN = 'tin'
    PHONE = 'phone'
    EMAIL = 'email'
    CUSTOM = 'custom'


RectTuple = tuple[float, float, float, float]


@dataclass(frozen=True)
class ExactValueRule:
    """An exact text value to search for."""

    category: RedactionCategory
    value: str
    case_sensitive: bool = False


@dataclass(frozen=True)
class PatternRule:
    """A named pattern-based redaction rule."""

    category: RedactionCategory
    pattern_name: str


@dataclass(frozen=True)
class RedactionRequest:
    """Input to the analysis engine."""

    input_path: Path
    exact_rules: list[ExactValueRule]
    pattern_rules: list[PatternRule]
    case_sensitive: bool = False


@dataclass(frozen=True)
class RedactionMatch:
    """A discovered redaction candidate in a document."""

    match_id: str
    category: RedactionCategory
    text: str
    page_number: int
    rects: list[RectTuple]
    context: str | None
    source_rule: str

    @property
    def occurrence_count(self) -> int:
        """Number of redaction rectangles attached to this match."""

        return len(self.rects)


@dataclass(frozen=True)
class DocumentAnalysis:
    """Analysis results for a PDF document."""

    page_count: int
    matches: list[RedactionMatch]
    warnings: list[str]


@dataclass(frozen=True)
class RedactionResult:
    """Output information after redactions are applied."""

    output_path: Path
    redaction_count: int


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


@dataclass(frozen=True)
class PDFFileInfo:
    """Basic metadata about a PDF selected in the UI."""

    path: Path
    file_size_bytes: int
    page_count: int
