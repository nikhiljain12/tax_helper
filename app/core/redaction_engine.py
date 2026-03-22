"""Scan and apply redactions for PDF documents."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import fitz  # PyMuPDF

from app.core.models import (
    DocumentAnalysis,
    ExactValueRule,
    PatternRule,
    RectTuple,
    RedactionMatch,
    RedactionRequest,
    RedactionResult,
)
from app.core.patterns import PATTERN_DEFINITIONS


class RedactionEngine:
    """Analyzes PDFs for reviewable matches and applies selected redactions."""

    def analyze(self, request: RedactionRequest) -> DocumentAnalysis:
        """Analyze a PDF and return reviewable redaction candidates."""

        input_path = self._validate_input_path(request.input_path)

        doc = self._open_document(input_path)
        try:
            matches: list[RedactionMatch] = []
            non_empty_pages = 0

            for page_index in range(len(doc)):
                page = doc[page_index]
                page_number = page_index + 1
                page_text = page.get_text('text')

                if page_text.strip():
                    non_empty_pages += 1

                matches.extend(
                    self._find_exact_matches(
                        page=page,
                        page_number=page_number,
                        page_text=page_text,
                        exact_rules=request.exact_rules,
                        default_case_sensitive=request.case_sensitive,
                    )
                )
                matches.extend(
                    self._find_pattern_matches(
                        page=page,
                        page_number=page_number,
                        page_text=page_text,
                        pattern_rules=request.pattern_rules,
                    )
                )

            warnings: list[str] = []
            if len(doc) > 0 and non_empty_pages == 0:
                warnings.append(
                    'This version supports text-based PDFs only. '
                    'Scanned or image-only PDFs require OCR before redaction.'
                )

            return DocumentAnalysis(
                page_count=len(doc),
                matches=self._merge_matches(matches),
                warnings=warnings,
            )
        finally:
            doc.close()

    def apply(
        self,
        input_path: Path,
        matches: list[RedactionMatch],
        selected_match_ids: set[str],
        output_path: Path,
    ) -> RedactionResult:
        """Apply selected redactions and save a new PDF."""

        if not selected_match_ids:
            raise ValueError('Select at least one redaction before saving.')

        source_path = self._validate_input_path(input_path)
        destination_path = Path(output_path)
        destination_path.parent.mkdir(parents=True, exist_ok=True)

        doc = self._open_document(source_path)
        redaction_count = 0
        selected_rects_by_page: dict[int, list[fitz.Rect]] = {}

        try:
            for match in matches:
                if match.match_id not in selected_match_ids:
                    continue

                page = doc[match.page_number - 1]
                for rect_tuple in match.rects:
                    rect = fitz.Rect(rect_tuple)
                    page.add_redact_annot(rect, fill=(0, 0, 0))
                    selected_rects_by_page.setdefault(match.page_number, []).append(rect)
                    redaction_count += 1

            if redaction_count == 0:
                raise ValueError('No selected redactions were found to apply.')

            for page_number, rects in selected_rects_by_page.items():
                self._remove_overlapping_annotations(doc[page_number - 1], rects)

            for page in doc:
                page.apply_redactions()

            try:
                doc.save(str(destination_path), garbage=4, deflate=True, clean=True)
            except Exception:
                if destination_path.exists():
                    destination_path.unlink(missing_ok=True)
                raise
        finally:
            doc.close()

        return RedactionResult(
            output_path=destination_path,
            redaction_count=redaction_count,
        )

    def _find_exact_matches(
        self,
        page: fitz.Page,
        page_number: int,
        page_text: str,
        exact_rules: list[ExactValueRule],
        default_case_sensitive: bool,
    ) -> list[RedactionMatch]:
        matches: list[RedactionMatch] = []

        for rule in exact_rules:
            search_text = rule.value.strip()
            if not search_text:
                continue

            rects = self._search_for_text(
                page=page,
                search_text=search_text,
                case_sensitive=rule.case_sensitive or default_case_sensitive,
            )
            if not rects:
                continue

            matches.append(
                RedactionMatch(
                    match_id=self._build_match_id(rule.category.value, page_number, search_text),
                    category=rule.category,
                    text=search_text,
                    page_number=page_number,
                    rects=rects,
                    context=self._build_context(page_text, search_text),
                    source_rule=f'exact:{rule.category.value}',
                )
            )

        return matches

    def _find_pattern_matches(
        self,
        page: fitz.Page,
        page_number: int,
        page_text: str,
        pattern_rules: list[PatternRule],
    ) -> list[RedactionMatch]:
        matches: list[RedactionMatch] = []

        for rule in pattern_rules:
            if rule.pattern_name not in PATTERN_DEFINITIONS:
                continue

            _, pattern = PATTERN_DEFINITIONS[rule.pattern_name]
            discovered_values = {match.group().strip() for match in pattern.finditer(page_text)}

            for match_text in sorted(filter(None, discovered_values)):
                rects = self._search_for_text(
                    page=page,
                    search_text=match_text,
                    case_sensitive=False,
                )
                if not rects:
                    continue

                matches.append(
                    RedactionMatch(
                        match_id=self._build_match_id(
                            f'{rule.category.value}:{rule.pattern_name}',
                            page_number,
                            match_text,
                        ),
                        category=rule.category,
                        text=match_text,
                        page_number=page_number,
                        rects=rects,
                        context=self._build_context(page_text, match_text),
                        source_rule=f'pattern:{rule.pattern_name}',
                    )
                )

        return matches

    def _search_for_text(
        self,
        page: fitz.Page,
        search_text: str,
        case_sensitive: bool,
    ) -> list[RectTuple]:
        rects = [self._rect_to_tuple(rect) for rect in page.search_for(search_text)]
        if not case_sensitive:
            return rects

        filtered_rects: list[RectTuple] = []
        expected = self._normalize_whitespace(search_text)
        for rect in rects:
            extracted = self._normalize_whitespace(page.get_textbox(fitz.Rect(rect)))
            if extracted == expected:
                filtered_rects.append(rect)
        return filtered_rects

    def _merge_matches(self, matches: list[RedactionMatch]) -> list[RedactionMatch]:
        merged: dict[tuple[str, int, str], RedactionMatch] = {}

        for match in matches:
            key = (match.category.value, match.page_number, match.text.lower())
            existing = merged.get(key)
            if existing is None:
                merged[key] = replace(
                    match,
                    rects=self._unique_rects(match.rects),
                )
                continue

            combined_rules = sorted(
                set(existing.source_rule.split('; ')) | set(match.source_rule.split('; '))
            )
            merged[key] = replace(
                existing,
                rects=self._unique_rects(existing.rects + match.rects),
                source_rule='; '.join(combined_rules),
                context=existing.context or match.context,
            )

        return sorted(
            merged.values(),
            key=lambda item: (item.category.value, item.page_number, item.text.lower()),
        )

    def _build_context(self, page_text: str, search_text: str) -> str | None:
        haystack = page_text.strip()
        needle = search_text.strip()
        if not haystack or not needle:
            return None

        lower_haystack = haystack.lower()
        lower_needle = needle.lower()
        index = lower_haystack.find(lower_needle)
        if index < 0:
            return None

        start = max(0, index - 30)
        end = min(len(haystack), index + len(needle) + 30)
        snippet = haystack[start:end].replace('\n', ' ')
        snippet = ' '.join(snippet.split())

        prefix = '...' if start > 0 else ''
        suffix = '...' if end < len(haystack) else ''
        return f'{prefix}{snippet}{suffix}'

    def _build_match_id(self, source: str, page_number: int, text: str) -> str:
        normalized_text = text.strip().lower()
        return f'{source}:{page_number}:{normalized_text}'

    def _open_document(self, input_path: Path) -> fitz.Document:
        try:
            doc = fitz.open(str(input_path))
        except Exception as exc:
            raise ValueError(f'Unable to open PDF file: {exc}') from exc

        if doc.needs_pass:
            doc.close()
            raise ValueError(
                'Password-protected PDFs are not supported in this version.'
            )

        return doc

    def _validate_input_path(self, input_path: Path) -> Path:
        path = Path(input_path)

        if not path.exists():
            raise FileNotFoundError(f'PDF file not found: {path}')
        if path.suffix.lower() != '.pdf':
            raise ValueError(f'File must be a PDF: {path}')

        return path

    def _rect_to_tuple(self, rect: fitz.Rect) -> RectTuple:
        return (float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1))

    def _normalize_whitespace(self, text: str) -> str:
        return ' '.join(text.split())

    def _unique_rects(self, rects: list[RectTuple]) -> list[RectTuple]:
        seen: set[RectTuple] = set()
        unique_rects: list[RectTuple] = []

        for rect in rects:
            rounded = tuple(round(value, 3) for value in rect)
            if rounded in seen:
                continue
            seen.add(rounded)
            unique_rects.append(rect)

        return unique_rects

    def _remove_overlapping_annotations(
        self,
        page: fitz.Page,
        redaction_rects: list[fitz.Rect],
    ) -> None:
        # Form fields and other annotations can render through appearance
        # streams that survive page-content redactions unless removed first.
        for widget in list(page.widgets() or []):
            widget_rect = fitz.Rect(widget.rect)
            if any(widget_rect.intersects(redaction_rect) for redaction_rect in redaction_rects):
                page.delete_widget(widget)

        for annot in list(page.annots() or []):
            annot_type, _ = annot.type
            if annot_type == fitz.PDF_ANNOT_REDACT:
                continue

            annot_rect = fitz.Rect(annot.rect)
            if any(annot_rect.intersects(redaction_rect) for redaction_rect in redaction_rects):
                page.delete_annot(annot)
