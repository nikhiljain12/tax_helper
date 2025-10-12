# PDF Sensitive Information Redactor

A Python tool for permanently redacting sensitive information from PDF documents, particularly useful for tax forms and documents containing personal information.

## Features

- **Exact String Matching**: Redact specific names, addresses, TINs, or any custom text
- **Pattern-Based Detection**: Auto-detect and redact TINs (SSN/EIN formats), phone numbers, and email addresses
- **Smart Format Conversion**: Automatically converts TIN to all SSN and EIN format variants
- **Permanent Redaction**: Text is completely removed from the PDF, not just visually covered
- **Case-Insensitive Search**: Optional case-sensitive or case-insensitive matching
- **Command-Line Interface**: Easy to use CLI with multiple options
- **Safe Operation**: Never modifies the original file

## Installation

1. Clone or download this repository
2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

Redact a specific name and TIN:
```bash
python main.py -i tax_form.pdf -o redacted.pdf --name "John Doe" --tin "123-45-6789"
```

### Auto-Detect Sensitive Patterns

Automatically find and redact TINs, phone numbers, and emails:
```bash
python main.py -i document.pdf --auto-detect
```

### Multiple Values

Redact multiple names or custom strings:
```bash
python main.py -i form.pdf --name "John Doe" --name "Jane Smith" --custom "Confidential"
```

### Custom Output Path

If no output path is specified, the tool creates `<input>_redacted.pdf`:
```bash
python main.py -i tax_form.pdf
# Creates: tax_form_redacted.pdf
```

## Command-Line Options

| Option | Description |
|--------|-------------|
| `-i, --input` | Input PDF file path (required) |
| `-o, --output` | Output PDF file path (default: `<input>_redacted.pdf`) |
| `--name` | Name(s) to redact (can be used multiple times) |
| `--address` | Address(es) to redact (can be used multiple times) |
| `--tin` | TIN(s) to redact - auto-converts to all SSN/EIN formats (can be used multiple times) |
| `--custom` | Custom string(s) to redact (can be used multiple times) |
| `--auto-detect` | Auto-detect TIN, phone, and email patterns |
| `--case-sensitive` | Perform case-sensitive matching |

## Examples

### Example 1: Redact Personal Information
```bash
python main.py -i tax_return.pdf \
  --name "John Smith" \
  --address "123 Main Street" \
  --tin "555-12-3456"
# Note: TIN will be redacted in all formats (SSN dashed, plain, EIN dashed, partially redacted)
```

### Example 2: Redact with Auto-Detection
```bash
python main.py -i document.pdf --auto-detect --name "Confidential Client"
```

### Example 3: Case-Sensitive Redaction
```bash
python main.py -i report.pdf --custom "TOP SECRET" --case-sensitive
```

### Example 4: Auto-Detect TIN Formats
```bash
python main.py -i business_tax_form.pdf --auto-detect
# Automatically detects all TIN formats: 123-45-6789, 123456789, xx-xxx-6789,
#                        XX-XXX-6789, **-***-6789, 12-3456789
```

### Example 5: Smart TIN Format Conversion
```bash
python main.py -i tax_form.pdf --tin "123456789"
# Automatically redacts all these formats:
# - 123-45-6789 (SSN dashed)
# - 123456789 (plain)
# - 12-3456789 (EIN dashed)
# - xx-xxx-6789, XX-XXX-6789, **-***-6789 (partially redacted)
```

## Pattern Detection

When using `--auto-detect`, the tool searches for:

- **TIN (Tax Identification Number)**: Multiple formats covering both SSN and EIN
  - SSN dashed: `XXX-XX-XXXX` (e.g., 123-45-6789)
  - EIN dashed: `XX-XXXXXXX` (e.g., 12-3456789)
  - Plain digits: `XXXXXXXXX` (e.g., 123456789)
  - Partially redacted with x: `xx-xxx-XXXX` or `XX-XXX-XXXX`
  - Partially redacted with asterisks: `**-***-XXXX`
- **Phone**: Format `XXX-XXX-XXXX`
- **Email**: Standard email address format

## Important Notes

### Limitations

1. **Text-Based PDFs Only**: This tool works with PDFs containing selectable text. Scanned PDFs (images) require OCR pre-processing.
2. **Layout Complexity**: Complex PDF layouts or unusual fonts may affect detection accuracy.
3. **Pattern Matching**: Auto-detection uses common formats. Non-standard formats may not be detected.

### Security Considerations

- Redactions are **permanent** and cannot be undone
- Text is removed from the underlying PDF data structure
- Original files are never modified (read-only access)
- Always verify redactions before sharing documents

## Project Structure

```
k1_analyzer/
├── main.py              # CLI entry point
├── pdf_redactor.py      # Core redaction logic
├── config.py            # Sensitive pattern configurations
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## Dependencies

- **PyMuPDF** (fitz): PDF manipulation library for reading, modifying, and redacting PDFs

## License

This project is provided as-is for educational and defensive security purposes only.

## Troubleshooting

### "Unable to open PDF file"
- Ensure the file is a valid PDF
- Check file permissions
- Try opening the PDF in a PDF reader to verify it's not corrupted

### "No matches found"
- Verify the text exists in the PDF (try copying text from the PDF)
- Check spelling of search terms
- Try without `--case-sensitive` flag
- For scanned PDFs, OCR processing is required first

### Output file not created
- Ensure you have write permissions in the output directory
- Check that disk space is available
- Verify at least one redaction was matched
