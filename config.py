"""Configuration for sensitive information patterns."""

import re

# Regex patterns for common sensitive information
SSN_PATTERN = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')
PHONE_PATTERN = re.compile(r'\b\d{3}-\d{3}-\d{4}\b')
EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')

# Dictionary of all sensitive patterns
SENSITIVE_PATTERNS = {
    'ssn': SSN_PATTERN,
    'phone': PHONE_PATTERN,
    'email': EMAIL_PATTERN
}
