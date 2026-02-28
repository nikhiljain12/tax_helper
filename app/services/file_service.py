"""File and PDF metadata helpers."""

from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF

from app.core.models import PDFFileInfo


class FileService:
    """Common file helpers used by the CLI and desktop UI."""

    def describe_pdf(self, input_path: str | Path) -> PDFFileInfo:
        """Return file metadata for a PDF."""

        path = Path(input_path)
        if not path.exists():
            raise FileNotFoundError(f'PDF file not found: {path}')
        if path.suffix.lower() != '.pdf':
            raise ValueError(f'File must be a PDF: {path}')

        try:
            doc = fitz.open(str(path))
        except Exception as exc:
            raise ValueError(f'Unable to open PDF file: {exc}') from exc

        try:
            if doc.needs_pass:
                raise ValueError(
                    'Password-protected PDFs are not supported in this version.'
                )
            return PDFFileInfo(
                path=path,
                file_size_bytes=path.stat().st_size,
                page_count=len(doc),
            )
        finally:
            doc.close()

    def default_output_path(self, input_path: str | Path) -> Path:
        """Build the default redacted output path."""

        path = Path(input_path)
        return path.parent / f'{path.stem}_redacted{path.suffix}'
