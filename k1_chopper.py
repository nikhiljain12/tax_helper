import base64
import json
import re

import anthropic

pdf_data = base64.b64encode(
    open('data/CVC_2024_K1_partnership_redacted.pdf', 'rb').read()
).decode('utf-8')

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

client = anthropic.Anthropic()

response = client.messages.create(
    model='claude-sonnet-4-5',
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
