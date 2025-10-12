#!/usr/bin/env python3
"""CLI interface for PDF redaction tool."""

import argparse
import sys
from pathlib import Path
from pdf_redactor import PDFRedactor
from config import SENSITIVE_PATTERNS, generate_tin_variants


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

    # Validate input file
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.parent / f"{input_path.stem}_redacted{input_path.suffix}"

    # Collect all strings to redact
    strings_to_redact = []

    if args.name:
        strings_to_redact.extend(args.name)

    if args.address:
        strings_to_redact.extend(args.address)

    if args.tin:
        # Generate all format variants for each TIN (both SSN and EIN formats)
        for tin in args.tin:
            variants = generate_tin_variants(tin)
            strings_to_redact.extend(variants)
            print(f"TIN variants generated: {len(variants)} formats for input '{tin}'")

    if args.custom:
        strings_to_redact.extend(args.custom)

    # Check if any redaction method is specified
    if not strings_to_redact and not args.auto_detect:
        print("Error: No redaction criteria specified. Use --name, --address, --tin, --custom, or --auto-detect",
              file=sys.stderr)
        sys.exit(1)

    try:
        print(f"Processing PDF: {input_path}")
        print(f"Output will be saved to: {output_path}")

        # Create redactor instance
        with PDFRedactor(str(input_path)) as redactor:
            print(f"PDF loaded successfully ({redactor.get_page_count()} pages)")

            total_redactions = 0

            # Redact exact strings
            if strings_to_redact:
                print(f"\nRedacting {len(strings_to_redact)} exact string(s)...")
                count = redactor.redact_exact_strings(strings_to_redact, args.case_sensitive)
                total_redactions += count
                print(f"  Applied {count} redaction(s)")

            # Redact patterns
            if args.auto_detect:
                print("\nAuto-detecting sensitive patterns (TIN, phone, email)...")
                count = redactor.redact_patterns(SENSITIVE_PATTERNS)
                total_redactions += count
                print(f"  Applied {count} redaction(s)")

            # Save the redacted PDF
            if total_redactions > 0:
                print(f"\nApplying {total_redactions} total redaction(s)...")
                redactor.save(str(output_path))
                print(f"✓ Redacted PDF saved successfully: {output_path}")
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
