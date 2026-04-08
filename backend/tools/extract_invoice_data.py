import base64
import json
import os
import tempfile
from pathlib import Path

import pdfplumber
from openai import AzureOpenAI
from langchain_core.tools import tool

EXTRACTION_PROMPT = (
    "Extract all invoice data and return ONLY valid JSON with this exact structure:\n"
    "{\n"
    '  "invoice_number": "",\n'
    '  "invoice_date": "",\n'
    '  "due_date": "",\n'
    '  "vendor_name": "",\n'
    '  "vendor_address": "",\n'
    '  "customer_name": "",\n'
    '  "line_items": [\n'
    '    {"description": "", "quantity": 0, "unit_price": 0.0, "line_total": 0.0}\n'
    "  ],\n"
    '  "subtotal": 0.0,\n'
    '  "tax": 0.0,\n'
    '  "total_amount": 0.0,\n'
    '  "currency": "USD",\n'
    '  "payment_terms": ""\n'
    "}\n"
    "Return ONLY the JSON object, no markdown, no explanation."
)


def _resolve_path(file_path: str) -> Path:
    """
    Return a local Path for the given file_path.

    If the path starts with ``s3://`` the object is downloaded to a temp file
    and its path is returned.  The caller is responsible for cleanup when
    using a temp file (detected by checking the parent dir).
    """
    if file_path.startswith("s3://"):
        import boto3
        # s3://bucket/prefix/file.ext  →  bucket, key
        without_scheme = file_path[len("s3://"):]
        bucket, _, key = without_scheme.partition("/")
        suffix = Path(key).suffix
        region = os.environ.get("AWS_REGION", "eu-west-2")
        s3 = boto3.client("s3", region_name=region)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        s3.download_fileobj(bucket, key, tmp)
        tmp.flush()
        tmp.close()
        return Path(tmp.name)
    return Path(file_path)


def _get_client() -> AzureOpenAI:
    return AzureOpenAI(
        api_key=os.environ["AZURE_OPENAI_KEY"],
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_version=os.environ["AZURE_OPENAI_API_VERSION"],
    )


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[1:end])
    return text.strip()


@tool
def extract_invoice_data(file_path: str) -> str:
    """Extract structured data from an invoice image or PDF file.
    Returns JSON with invoice_number, invoice_date, due_date, vendor_name,
    vendor_address, customer_name, line_items, subtotal, tax, total_amount,
    currency, and payment_terms."""
    tmp_path: Path | None = None
    try:
        path = _resolve_path(file_path)
        if file_path.startswith("s3://"):
            tmp_path = path  # remember for cleanup
        if not path.exists():
            return json.dumps({"error": f"File not found: {file_path}"})

        deployment = os.environ["AZURE_OPENAI_DEPLOYMENT"]
        client = _get_client()
        suffix = path.suffix.lower()

        if suffix == ".pdf":
            with pdfplumber.open(path) as pdf:
                pages_text = "\n".join(
                    page.extract_text() or "" for page in pdf.pages
                )

            response = client.chat.completions.create(
                model=deployment,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Here is the text extracted from an invoice PDF:\n\n"
                            f"{pages_text}\n\n"
                            f"{EXTRACTION_PROMPT}"
                        ),
                    }
                ],
                max_tokens=2048,
            )
        else:
            with open(path, "rb") as f:
                file_b64 = base64.standard_b64encode(f.read()).decode("utf-8")

            mime = "image/png" if suffix == ".png" else "image/jpeg"

            response = client.chat.completions.create(
                model=deployment,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime};base64,{file_b64}",
                                    "detail": "high",
                                },
                            },
                            {"type": "text", "text": EXTRACTION_PROMPT},
                        ],
                    }
                ],
                max_tokens=2048,
            )

        raw = _strip_fences(response.choices[0].message.content or "")
        return raw

    except Exception as e:
        return json.dumps({"error": str(e)})

    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass
