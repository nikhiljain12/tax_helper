"""Pattern definitions for sensitive information detection."""

from __future__ import annotations

import re

from app.core.models import RedactionCategory

PATTERN_DEFINITIONS: dict[str, tuple[RedactionCategory, re.Pattern[str]]] = {
    'ssn_dashed': (
        RedactionCategory.TIN,
        re.compile(r'(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)'),
    ),
    'ssn_plain': (
        RedactionCategory.TIN,
        re.compile(r'(?<!\d)\d{9}(?!\d)'),
    ),
    'ssn_partial_x': (
        RedactionCategory.TIN,
        re.compile(r'(?<!\w)[xX]{3}-[xX]{2}-\d{4}(?!\d)'),
    ),
    'ssn_partial_asterisk': (
        RedactionCategory.TIN,
        re.compile(r'\*{3}-\*{2}-\d{4}(?!\d)'),
    ),
    'ein_dashed': (
        RedactionCategory.TIN,
        re.compile(r'(?<!\d)\d{2}-\d{7}(?!\d)'),
    ),
    'ein_plain': (
        RedactionCategory.TIN,
        re.compile(r'(?<!\d)\d{9}(?!\d)'),
    ),
    'phone': (
        RedactionCategory.PHONE,
        re.compile(r'(?<!\d)\d{3}-\d{3}-\d{4}(?!\d)'),
    ),
    'email': (
        RedactionCategory.EMAIL,
        re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'),
    ),
}


SENSITIVE_PATTERNS: dict[str, re.Pattern[str]] = {
    name: pattern for name, (_, pattern) in PATTERN_DEFINITIONS.items()
}


AUTO_DETECT_PATTERN_NAMES = frozenset(PATTERN_DEFINITIONS)
