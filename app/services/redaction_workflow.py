"""Shared workflow helpers for the CLI and desktop UI."""

from __future__ import annotations

from pathlib import Path

from app.core.models import ExactValueRule, PatternRule, RedactionCategory, RedactionRequest
from app.core.patterns import PATTERN_DEFINITIONS
from app.core.tin import generate_tin_variants
from app.services.file_service import FileService


class RedactionWorkflowService:
    """Builds normalized requests for the redaction engine."""

    def __init__(self) -> None:
        self.file_service = FileService()

    def build_request(
        self,
        input_path: str | Path,
        names: list[str] | None = None,
        addresses: list[str] | None = None,
        tins: list[str] | None = None,
        custom_strings: list[str] | None = None,
        detect_tin: bool = False,
        detect_phone: bool = False,
        detect_email: bool = False,
        case_sensitive: bool = False,
    ) -> RedactionRequest:
        """Normalize UI or CLI selections into a redaction request."""

        exact_rules: list[ExactValueRule] = []
        pattern_rules: list[PatternRule] = []

        exact_rules.extend(
            self._build_exact_rules(RedactionCategory.NAME, names, case_sensitive)
        )
        exact_rules.extend(
            self._build_exact_rules(
                RedactionCategory.ADDRESS,
                addresses,
                case_sensitive,
            )
        )
        exact_rules.extend(
            self._build_tin_rules(tins, case_sensitive)
        )
        exact_rules.extend(
            self._build_exact_rules(
                RedactionCategory.CUSTOM,
                custom_strings,
                case_sensitive,
            )
        )

        if detect_tin:
            pattern_rules.extend(
                PatternRule(category=category, pattern_name=pattern_name)
                for pattern_name, (category, _) in PATTERN_DEFINITIONS.items()
                if category == RedactionCategory.TIN
            )
        if detect_phone:
            pattern_rules.append(
                PatternRule(
                    category=RedactionCategory.PHONE,
                    pattern_name='phone',
                )
            )
        if detect_email:
            pattern_rules.append(
                PatternRule(
                    category=RedactionCategory.EMAIL,
                    pattern_name='email',
                )
            )

        if not exact_rules and not pattern_rules:
            raise ValueError(
                'No redaction criteria specified. Add exact values or enable '
                'auto-detect for TIN, phone, or email.'
            )

        return RedactionRequest(
            input_path=Path(input_path),
            exact_rules=exact_rules,
            pattern_rules=pattern_rules,
            case_sensitive=case_sensitive,
        )

    def parse_multivalue_text(self, raw_text: str) -> list[str]:
        """Split a textarea value into trimmed entries."""

        values: list[str] = []
        for line in raw_text.splitlines():
            normalized = line.strip()
            if normalized:
                values.append(normalized)
        return values

    def default_output_path(self, input_path: str | Path) -> Path:
        """Expose the file service's default output path."""

        return self.file_service.default_output_path(input_path)

    def _build_exact_rules(
        self,
        category: RedactionCategory,
        values: list[str] | None,
        case_sensitive: bool,
    ) -> list[ExactValueRule]:
        rules: list[ExactValueRule] = []

        for value in values or []:
            normalized = value.strip()
            if not normalized:
                continue
            rules.append(
                ExactValueRule(
                    category=category,
                    value=normalized,
                    case_sensitive=case_sensitive,
                )
            )

        return rules

    def _build_tin_rules(
        self,
        tins: list[str] | None,
        case_sensitive: bool,
    ) -> list[ExactValueRule]:
        tin_rules: list[ExactValueRule] = []
        seen: set[str] = set()

        for tin in tins or []:
            for variant in generate_tin_variants(tin.strip()):
                normalized = variant.strip()
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                tin_rules.append(
                    ExactValueRule(
                        category=RedactionCategory.TIN,
                        value=normalized,
                        case_sensitive=case_sensitive,
                    )
                )

        return tin_rules
