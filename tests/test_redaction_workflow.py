"""Tests for the shared redaction workflow and engine."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import fitz  # PyMuPDF

from app.core.models import RedactionCategory
from app.core.redaction_engine import RedactionEngine
from app.services.file_service import FileService
from app.services.redaction_workflow import RedactionWorkflowService


class RedactionWorkflowTests(unittest.TestCase):
    """End-to-end tests for request building, analysis, and apply flows."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.workflow = RedactionWorkflowService()
        self.engine = RedactionEngine()
        self.file_service = FileService()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_build_request_expands_tin_variants_and_detect_rules(self) -> None:
        request = self.workflow.build_request(
            input_path=self.temp_path / 'input.pdf',
            names=['John Doe'],
            tins=['123-45-6789'],
            detect_phone=True,
            detect_email=True,
        )

        exact_pairs = {(rule.category.value, rule.value) for rule in request.exact_rules}
        pattern_pairs = {(rule.category.value, rule.pattern_name) for rule in request.pattern_rules}

        self.assertIn(('name', 'John Doe'), exact_pairs)
        self.assertIn(('tin', '123-45-6789'), exact_pairs)
        self.assertIn(('tin', '123456789'), exact_pairs)
        self.assertIn(('phone', 'phone'), pattern_pairs)
        self.assertIn(('email', 'email'), pattern_pairs)

    def test_analyze_and_apply_selected_matches(self) -> None:
        input_path = self.temp_path / 'sample.pdf'
        output_path = self.temp_path / 'sample_redacted.pdf'
        self._create_text_pdf(
            input_path,
            (
                'John Doe lives at 123 Main Street.\n'
                'SSN: 123-45-6789\n'
                'Email: john@example.com\n'
                'Phone: 555-111-2222\n'
            ),
        )

        request = self.workflow.build_request(
            input_path=input_path,
            names=['John Doe'],
            addresses=['123 Main Street'],
            tins=['123-45-6789'],
            detect_phone=True,
            detect_email=True,
        )

        analysis = self.engine.analyze(request)

        self.assertEqual(1, analysis.page_count)
        self.assertFalse(analysis.warnings)
        self.assertGreaterEqual(len(analysis.matches), 5)

        categories = {match.category for match in analysis.matches}
        self.assertEqual(
            {
                RedactionCategory.NAME,
                RedactionCategory.ADDRESS,
                RedactionCategory.TIN,
                RedactionCategory.PHONE,
                RedactionCategory.EMAIL,
            },
            categories,
        )

        selected_ids = {
            match.match_id
            for match in analysis.matches
            if match.category in {RedactionCategory.NAME, RedactionCategory.TIN}
        }

        result = self.engine.apply(
            input_path=input_path,
            matches=analysis.matches,
            selected_match_ids=selected_ids,
            output_path=output_path,
        )

        self.assertTrue(result.output_path.exists())
        self.assertGreaterEqual(result.redaction_count, 2)

        original_text = self._extract_text(input_path)
        redacted_text = self._extract_text(output_path)

        self.assertIn('John Doe', original_text)
        self.assertIn('123-45-6789', original_text)
        self.assertNotIn('John Doe', redacted_text)
        self.assertNotIn('123-45-6789', redacted_text)
        self.assertIn('john@example.com', redacted_text)
        self.assertIn('555-111-2222', redacted_text)

    def test_blank_pdf_returns_scanned_warning(self) -> None:
        input_path = self.temp_path / 'blank.pdf'
        self._create_blank_pdf(input_path)

        request = self.workflow.build_request(
            input_path=input_path,
            custom_strings=['Anything'],
        )

        analysis = self.engine.analyze(request)

        self.assertEqual([], analysis.matches)
        self.assertEqual(1, len(analysis.warnings))
        self.assertIn('text-based PDFs only', analysis.warnings[0])

    def test_apply_removes_overlapping_form_widgets(self) -> None:
        input_path = self.temp_path / 'widget_sample.pdf'
        output_path = self.temp_path / 'widget_sample_redacted.pdf'
        self._create_pdf_with_text_widget(
            input_path,
            static_text='Name: Nikhil Jain',
            widget_value='123-45-6789',
        )

        request = self.workflow.build_request(
            input_path=input_path,
            names=['Nikhil Jain'],
            detect_tin=True,
        )

        analysis = self.engine.analyze(request)
        result = self.engine.apply(
            input_path=input_path,
            matches=analysis.matches,
            selected_match_ids={match.match_id for match in analysis.matches},
            output_path=output_path,
        )

        self.assertTrue(result.output_path.exists())

        doc = fitz.open(str(output_path))
        try:
            page = doc[0]
            self.assertNotIn('Nikhil Jain', page.get_text('text'))
            self.assertNotIn('123-45-6789', page.get_text('text'))
            self.assertEqual([], list(page.widgets() or []))
        finally:
            doc.close()

    def test_apply_removes_overlapping_freetext_annotations(self) -> None:
        input_path = self.temp_path / 'annot_sample.pdf'
        output_path = self.temp_path / 'annot_sample_redacted.pdf'
        self._create_pdf_with_freetext_annot(
            input_path,
            static_text='Name: Nikhil Jain',
            annot_text='123-45-6789',
        )

        request = self.workflow.build_request(
            input_path=input_path,
            names=['Nikhil Jain'],
            detect_tin=True,
        )

        analysis = self.engine.analyze(request)
        result = self.engine.apply(
            input_path=input_path,
            matches=analysis.matches,
            selected_match_ids={match.match_id for match in analysis.matches},
            output_path=output_path,
        )

        self.assertTrue(result.output_path.exists())

        doc = fitz.open(str(output_path))
        try:
            page = doc[0]
            self.assertNotIn('Nikhil Jain', page.get_text('text'))
            self.assertNotIn('123-45-6789', page.get_text('text'))
            self.assertEqual([], list(page.annots() or []))
        finally:
            doc.close()

    def test_default_output_path_appends_redacted_suffix(self) -> None:
        expected = self.temp_path / 'document_redacted.pdf'
        actual = self.file_service.default_output_path(self.temp_path / 'document.pdf')
        self.assertEqual(expected, actual)

    def _create_text_pdf(self, path: Path, text: str) -> None:
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), text)
        doc.save(path)
        doc.close()

    def _create_blank_pdf(self, path: Path) -> None:
        doc = fitz.open()
        doc.new_page()
        doc.save(path)
        doc.close()

    def _create_pdf_with_text_widget(
        self,
        path: Path,
        static_text: str,
        widget_value: str,
    ) -> None:
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), static_text)

        widget = fitz.Widget()
        widget.field_name = 'sensitive_field'
        widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
        widget.field_value = widget_value
        widget.rect = fitz.Rect(72, 100, 220, 120)
        page.add_widget(widget)

        doc.save(path)
        doc.close()

    def _create_pdf_with_freetext_annot(
        self,
        path: Path,
        static_text: str,
        annot_text: str,
    ) -> None:
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), static_text)
        page.add_freetext_annot(fitz.Rect(72, 100, 220, 130), annot_text)
        doc.save(path)
        doc.close()

    def _extract_text(self, path: Path) -> str:
        doc = fitz.open(str(path))
        try:
            return '\n'.join(page.get_text('text') for page in doc)
        finally:
            doc.close()


if __name__ == '__main__':
    unittest.main()
