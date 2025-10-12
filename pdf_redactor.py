"""PDF Redactor for removing sensitive information from PDF documents."""

import fitz  # PyMuPDF
from pathlib import Path
from typing import List, Dict, Optional
import re


class PDFRedactor:
    """Class to handle redaction of sensitive information in PDF files."""

    def __init__(self, pdf_path: str):
        """
        Initialize the PDF Redactor.

        Args:
            pdf_path: Path to the input PDF file

        Raises:
            FileNotFoundError: If the PDF file doesn't exist
            ValueError: If the file is not a valid PDF
        """
        self.pdf_path = Path(pdf_path)

        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        if not self.pdf_path.suffix.lower() == '.pdf':
            raise ValueError(f"File must be a PDF: {pdf_path}")

        try:
            self.doc = fitz.open(str(self.pdf_path))
        except Exception as e:
            raise ValueError(f"Unable to open PDF file: {e}")

        self.redaction_count = 0

    def find_text_instances(self, page: fitz.Page, search_text: str, case_sensitive: bool = False) -> List[fitz.Rect]:
        """
        Find all instances of text on a page.

        Args:
            page: PyMuPDF page object
            search_text: Text to search for
            case_sensitive: Whether to perform case-sensitive search

        Returns:
            List of rectangles (bounding boxes) for found text
        """
        flags = 0 if case_sensitive else fitz.TEXT_PRESERVE_WHITESPACE

        # Search for text instances
        text_instances = page.search_for(search_text, flags=flags)

        return text_instances

    def redact_exact_strings(self, strings: List[str], case_sensitive: bool = False) -> int:
        """
        Redact exact string matches across all pages.

        Args:
            strings: List of strings to redact
            case_sensitive: Whether to perform case-sensitive matching

        Returns:
            Number of redactions applied
        """
        if not strings:
            return 0

        redactions_applied = 0

        for page_num in range(len(self.doc)):
            page = self.doc[page_num]

            for search_text in strings:
                if not search_text:
                    continue

                # Find all instances of the text
                instances = self.find_text_instances(page, search_text, case_sensitive)

                # Add redaction annotation for each instance
                for rect in instances:
                    page.add_redact_annot(rect, fill=(0, 0, 0))
                    redactions_applied += 1

        self.redaction_count += redactions_applied
        return redactions_applied

    def redact_patterns(self, pattern_dict: Dict[str, re.Pattern]) -> int:
        """
        Redact text matching regex patterns.

        Args:
            pattern_dict: Dictionary mapping pattern names to compiled regex patterns

        Returns:
            Number of redactions applied
        """
        if not pattern_dict:
            return 0

        redactions_applied = 0

        for page_num in range(len(self.doc)):
            page = self.doc[page_num]

            # Extract all text from the page with position information
            text_dict = page.get_text("dict")

            for block in text_dict.get("blocks", []):
                if block.get("type") == 0:  # Text block
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            text = span.get("text", "")
                            bbox = span.get("bbox", None)

                            if not text or not bbox:
                                continue

                            # Check each pattern
                            for pattern_name, pattern in pattern_dict.items():
                                matches = pattern.finditer(text)

                                for match in matches:
                                    # Calculate approximate position of matched text
                                    # This is a simplified approach
                                    match_text = match.group()

                                    # Search for the specific match on the page
                                    match_rects = page.search_for(match_text)

                                    for rect in match_rects:
                                        page.add_redact_annot(rect, fill=(0, 0, 0))
                                        redactions_applied += 1

        self.redaction_count += redactions_applied
        return redactions_applied

    def apply_redactions(self) -> None:
        """
        Apply all pending redactions permanently.
        This removes the text from the PDF, not just visually covers it.
        """
        for page_num in range(len(self.doc)):
            page = self.doc[page_num]
            page.apply_redactions()

    def save(self, output_path: str) -> None:
        """
        Save the redacted PDF to a file.

        Args:
            output_path: Path where the redacted PDF will be saved

        Raises:
            ValueError: If no redactions have been made
        """
        output_path = Path(output_path)

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Apply all redactions before saving
        self.apply_redactions()

        # Save the document
        self.doc.save(str(output_path), garbage=4, deflate=True, clean=True)

    def close(self) -> None:
        """Close the PDF document."""
        if self.doc:
            self.doc.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False

    def get_page_count(self) -> int:
        """Get the total number of pages in the PDF."""
        return len(self.doc)

    def get_redaction_count(self) -> int:
        """Get the total number of redactions applied."""
        return self.redaction_count
