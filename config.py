"""Configuration for sensitive information patterns."""

import re

# Regex patterns for common sensitive information

# SSN Patterns - Multiple formats
SSN_PATTERN_DASHED = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')  # 123-45-6789
SSN_PATTERN_PLAIN = re.compile(r'\b\d{9}\b')  # 123456789
SSN_PATTERN_PARTIAL_X = re.compile(r'\b[xX]{2}-[xX]{3}-\d{4}\b')  # xx-xxx-6789 or XX-XXX-6789
SSN_PATTERN_PARTIAL_ASTERISK = re.compile(r'\b\*{2}-\*{3}-\d{4}\b')  # **-***-6789

# EIN Patterns - Multiple formats
EIN_PATTERN_DASHED = re.compile(r'\b\d{2}-\d{7}\b')  # 12-3456789
EIN_PATTERN_PLAIN = re.compile(r'(?<!\d)\b\d{9}\b(?!\d)')  # 123456789 (overlaps with SSN, but both should be redacted)

# Other patterns
PHONE_PATTERN = re.compile(r'\b\d{3}-\d{3}-\d{4}\b')
EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')

# Dictionary of all sensitive patterns
SENSITIVE_PATTERNS = {
    'ssn_dashed': SSN_PATTERN_DASHED,
    'ssn_plain': SSN_PATTERN_PLAIN,
    'ssn_partial_x': SSN_PATTERN_PARTIAL_X,
    'ssn_partial_asterisk': SSN_PATTERN_PARTIAL_ASTERISK,
    'ein_dashed': EIN_PATTERN_DASHED,
    'ein_plain': EIN_PATTERN_PLAIN,
    'phone': PHONE_PATTERN,
    'email': EMAIL_PATTERN
}


def generate_tin_variants(tin: str) -> list[str]:
    """
    Generate all format variants of a TIN (Tax Identification Number).
    TIN encompasses both SSN and EIN formats since they can overlap.

    Args:
        tin: TIN in any supported format (SSN or EIN)

    Returns:
        List of all TIN format variants (both SSN and EIN formats)
    """
    # Extract digits only
    digits = ''.join(c for c in tin if c.isdigit())

    if len(digits) != 9:
        # If not exactly 9 digits, return original
        return [tin]

    # Generate all variants (both SSN and EIN formats)
    variants = [
        # SSN formats
        f"{digits[0:3]}-{digits[3:5]}-{digits[5:9]}",  # 123-45-6789
        f"xx-xxx-{digits[5:9]}",                        # xx-xxx-6789
        f"XX-XXX-{digits[5:9]}",                        # XX-XXX-6789
        f"**-***-{digits[5:9]}",                        # **-***-6789
        # EIN formats
        f"{digits[0:2]}-{digits[2:9]}",                 # 12-3456789
        # Plain format (works for both SSN and EIN)
        digits                                          # 123456789
    ]

    return variants
