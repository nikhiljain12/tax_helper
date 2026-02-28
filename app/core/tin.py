"""Helpers for working with TIN/SSN/EIN variants."""

from __future__ import annotations


def generate_tin_variants(tin: str) -> list[str]:
    """
    Generate supported display variants for a nine-digit TIN.

    The utility accepts either SSN or EIN input and returns common forms that
    may appear in tax PDFs.
    """

    digits = ''.join(char for char in tin if char.isdigit())

    if len(digits) != 9:
        return [tin]

    return [
        f'{digits[0:3]}-{digits[3:5]}-{digits[5:9]}',
        f'xx-xxx-{digits[5:9]}',
        f'XX-XXX-{digits[5:9]}',
        f'**-***-{digits[5:9]}',
        f'{digits[0:2]}-{digits[2:9]}',
        digits,
    ]
