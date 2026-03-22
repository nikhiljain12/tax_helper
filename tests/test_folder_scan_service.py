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
