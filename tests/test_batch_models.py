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
