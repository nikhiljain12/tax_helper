#!/usr/bin/env python3
"""CLI interface for PDF redaction tool."""

import argparse
import sys
from pathlib import Path

from app.core.redaction_engine import RedactionEngine
from app.core.tin import generate_tin_variants
from app.services.redaction_workflow import RedactionWorkflowService


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Redact sensitive information from PDF documents',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s -i tax_form.pdf -o redacted.pdf --name "John Doe" --tin "123-45-6789"
  %(prog)s -i document.pdf --auto-detect
  %(prog)s -i form.pdf --custom "Sensitive Info" --custom "Confidential"
  %(prog)s -i business.pdf --tin "123456789"
        '''
    )

    parser.add_argument(
        '-i', '--input',
        required=True,
        help='Input PDF file path'
    )

    parser.add_argument(
        '-o', '--output',
        help='Output PDF file path (default: <input>_redacted.pdf)'
    )

    parser.add_argument(
        '--name',
        action='append',
        help='Name(s) to redact (can be used multiple times)'
    )

    parser.add_argument(
        '--address',
        action='append',
        help='Address(es) to redact (can be used multiple times)'
    )

    parser.add_argument(
        '--tin',
        action='append',
        help='TIN(s) to redact in all formats (SSN/EIN) - can be used multiple times'
    )

    parser.add_argument(
        '--custom',
        action='append',
        help='Custom string(s) to redact (can be used multiple times)'
    )

    parser.add_argument(
        '--auto-detect',
        action='store_true',
        help='Auto-detect and redact TIN (SSN/EIN formats), phone, and email patterns'
    )

    parser.add_argument(
        '--case-sensitive',
        action='store_true',
        help='Perform case-sensitive matching for exact strings'
    )

    return parser.parse_args()


def main():
    """Main execution function."""
    args = parse_arguments()
    workflow = RedactionWorkflowService()
    engine = RedactionEngine()

    # Validate input file
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = workflow.default_output_path(input_path)

    try:
        request = workflow.build_request(
            input_path=input_path,
            names=args.name,
            addresses=args.address,
            tins=args.tin,
            custom_strings=args.custom,
            detect_tin=args.auto_detect,
            detect_phone=args.auto_detect,
            detect_email=args.auto_detect,
            case_sensitive=args.case_sensitive,
        )

        print(f"Processing PDF: {input_path}")
        print(f"Output will be saved to: {output_path}")
        if args.tin:
            for tin in args.tin:
                variant_count = len(set(generate_tin_variants(tin)))
                print(
                    f"TIN variants generated for '{tin}': "
                    f'{variant_count} candidate format(s)'
                )

        analysis = engine.analyze(request)
        print(f"PDF loaded successfully ({analysis.page_count} pages)")

        if analysis.warnings:
            for warning in analysis.warnings:
                print(f"Warning: {warning}")

        total_redactions = sum(match.occurrence_count for match in analysis.matches)

        if total_redactions > 0:
            print(f"\nFound {len(analysis.matches)} reviewable match(es)")
            print(f"Applying {total_redactions} total redaction annotation(s)...")
            result = engine.apply(
                input_path=input_path,
                matches=analysis.matches,
                selected_match_ids={match.match_id for match in analysis.matches},
                output_path=output_path,
            )
            print(f"✓ Redacted PDF saved successfully: {result.output_path}")
        else:
            print("\nWarning: No matches found. No redactions applied.")
            print("The output file will not be created.")

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
