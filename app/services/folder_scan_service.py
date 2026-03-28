"""Recursive PDF discovery and output-path mirroring for batch redaction."""

from __future__ import annotations

from pathlib import Path

from app.core.models import BatchFileItem


class FolderScanService:
    """Scans a folder recursively and builds a list of input→output file pairs."""

    def scan(self, input_folder: Path, output_folder: Path) -> list[BatchFileItem]:
        """Return sorted BatchFileItems for all non-redacted PDFs under input_folder."""

        items: list[BatchFileItem] = []
        all_files = sorted(
            p for p in input_folder.rglob('*') if p.suffix.lower() == '.pdf'
        )
        for pdf_path in all_files:
            if 'redacted' in pdf_path.stem.lower():
                continue
            relative = pdf_path.relative_to(input_folder)
            output_path = output_folder / relative.parent / f'{pdf_path.stem}_redacted.pdf'
            items.append(BatchFileItem(input_path=pdf_path, output_path=output_path))
        return items
