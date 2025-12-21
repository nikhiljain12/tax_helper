import base64
import json
import re

import anthropic
import fitz  # PyMuPDF
from openai import OpenAI

filename = 'CVC_2024_K1_partnership_redacted.pdf'
datadir = 'data'
pdf_data = base64.b64encode(open(f'{datadir}/{filename}', 'rb').read()).decode('utf-8')

task_prompt = """
This PDF contains partnership tax information (form K-1 etc). 
It contains Federal Form K-1, Federal Form K-3 and state forms which are 
also usually called K-1s. Some states may not call it a K-1. 
Which states are included in the package is not known beforehand.

Analyze the pdf and output the page numbers for each of the following forms in JSON format:
{
    "federal_k1_pages": { "first_page": <page_number>, "last_page": <page_number> },
    "federal_k3_pages": { "first_page": <page_number>, "last_page": <page_number> },
    "state_k1_pages": {
        "state_abbreviation": { "first_page": <page_number>, "last_page": <page_number> },
        ...
    }
}

IMPORTANT:
* Page numbers should be 1-indexed. 
* Use logical page numbers. i.e. Calculate the page numbers based on the page breaks in the PDF, not based on the page numbers printed on the forms.
* To identify the start of a state K-1 form, look for the state abbreviation or full state name in the header of the form.
* Once a form starts, it usually continues until the start of the next form (Federal K-1, Federal K-3 or another state K-1).
* If there are no state K-1 forms, return an empty object for "state_k1_pages".

Example output:
{
    "federal_k1_pages": { "first_page": 1, "last_page": 4 },
    "federal_k3_pages": { "first_page": 5, "last_page": 6 },
    "state_k1_pages": {
        "CA": { "first_page": 7, "last_page": 8 },
        "NY": { "first_page": 9, "last_page": 10 }
    }
}
"""


def fetch_using_anthropic():
    client = anthropic.Anthropic()

    response = client.messages.create(
        model='claude-haiku-4-5-20251001',  # 'claude-sonnet-4-5',
        max_tokens=1024,
        messages=[
            {
                'role': 'user',
                'content': [
                    {
                        'type': 'document',
                        'source': {
                            'type': 'base64',
                            'media_type': 'application/pdf',
                            'data': pdf_data,
                        },
                    },
                    {
                        'type': 'text',  # 'instruction',
                        'text': task_prompt,
                    },
                ],
            },
        ],
    )

    json_str = response.content[0].text
    print(json_str)
    # Remove markdown code block markers if present
    json_str_clean = re.sub(r'^```json\s*|\s*```$', '', json_str.strip())

    # Parse the JSON string
    data = json.loads(json_str_clean)
    print(data)
    return data


def fetch_using_openai():
    client = OpenAI()

    response = client.responses.create(
        model='gpt-5.1',
        service_tier='flex',
        input=[
            {
                'role': 'user',
                'content': [
                    {
                        'type': 'input_text',
                        'text': task_prompt,
                    },
                    {
                        'type': 'input_file',
                        'filename': filename,
                        'file_data': f'data:application/pdf;base64,{pdf_data}',
                    },
                ],
            }
        ],
    )

    print(response.output_text)
    return json.loads(response.output_text)


def extract_pdf_pages(input_pdf_path, start_page, end_page):
    """
    Extract pages from a PDF file and return an in-memory PDF representation.

    Args:
        input_pdf_path: Path to the input PDF file
        start_page: First page to extract (1-indexed)
        end_page: Last page to extract (1-indexed, inclusive)

    Returns:
        bytes: PDF data as bytes, or None if an error occurred
    """

    if start_page is None or end_page is None or start_page < 1 or end_page < 1:
        print('Invalid page numbers provided for extraction.')
        return None

    try:
        with fitz.open(input_pdf_path) as pdf_document:
            # Convert 1-indexed page numbers to 0-indexed
            start_idx = start_page - 1
            end_idx = end_page - 1

            # Validate page numbers
            if start_idx < 0 or end_idx >= pdf_document.page_count:
                print(
                    f'Error: Invalid page range. PDF has {pdf_document.page_count} pages.'
                )
                return None

            if start_idx > end_idx:
                print('Error: start_page must be less than or equal to end_page')
                return None

            # Create a new PDF for the output and extract pages
            with fitz.open() as output_pdf:
                output_pdf.insert_pdf(
                    pdf_document, from_page=start_idx, to_page=end_idx
                )
                pdf_bytes = output_pdf.tobytes()

        print(
            f'Successfully extracted pages {start_page}-{end_page} ({len(pdf_bytes)} bytes)'
        )
        return pdf_bytes

    except Exception as e:
        print(f'Error extracting pages: {e}')
        return None


def chop_k1():
    data = fetch_using_openai()
    fed_page_nums = data.get('federal_k1_pages', {})
    state_page_nums = data.get('state_k1_pages', {})
    print(f'Federal K-1 pages: {fed_page_nums}')
    # TODO: call function to chop the PDF based on these page numbers
    fed_k1_pdf = extract_pdf_pages(
        f'{datadir}/{filename}',
        fed_page_nums.get('first_page'),
        fed_page_nums.get('last_page'),
    )


if __name__ == '__main__':
    # fetch_using_anthropic()
    fetch_using_openai()
