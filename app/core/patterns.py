"""Pattern definitions for sensitive information detection."""

from __future__ import annotations

import re

from app.core.models import RedactionCategory

PATTERN_DEFINITIONS: dict[str, tuple[RedactionCategory, re.Pattern[str]]] = {
    'ssn_dashed': (
        RedactionCategory.TIN,
        re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
    ),
    'ssn_plain': (
        RedactionCategory.TIN,
        re.compile(r'\b\d{9}\b'),
    ),
    'ssn_partial_x': (
        RedactionCategory.TIN,
        re.compile(r'\b[xX]{3}-[xX]{2}-\d{4}\b'),
    ),
    'ssn_partial_asterisk': (
        RedactionCategory.TIN,
        re.compile(r'\b\*{3}-\*{2}-\d{4}\b'),
    ),
    'ein_dashed': (
        RedactionCategory.TIN,
        re.compile(r'\b\d{2}-\d{7}\b'),
    ),
    'ein_plain': (
        RedactionCategory.TIN,
        re.compile(r'(?<!\d)\b\d{9}\b(?!\d)'),
    ),
    'phone': (
        RedactionCategory.PHONE,
        re.compile(r'\b\d{3}-\d{3}-\d{4}\b'),
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
