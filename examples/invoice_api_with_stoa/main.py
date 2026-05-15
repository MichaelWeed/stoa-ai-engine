"""
Invoice Processor — with Stoa

Functionally identical to invoice_api/main.py, but with three changes:
  1. The LLM is called ONCE to generate an extraction plan.
  2. Every subsequent request executes that plan as plain Python code.
  3. A budget enforcer and policy gateway protect the endpoint.

What changes for the developer:
  - Replace the OpenAI client call with runner.run_inline()
  - Remove prompt engineering (Stoa handles that internally)
  - Add an OPENAI_API_KEY for the first run; remove it entirely
    if you ship the pre-cached plan (see README)

What the user never sees changing:
  - The FastAPI surface (same request/response shape)
  - The business logic (same extraction rules)
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from stoa.runner import WorkflowRunner

app = FastAPI(title="Invoice Processor (with Stoa)")

# One runner, shared across requests. Planning is cached after the first call.
runner = WorkflowRunner()

# The task description is the only prompt you write.
# Stoa converts this into executable Python code and caches it.
EXTRACTION_TASK = """
Extract the following from the invoice text in `inputs.raw_text`:
  - vendor (string): company name from the header
  - total_usd (float): the final total amount due
  - line_items (list): each item as {description, quantity, unit_price_usd}

Return a single JSON object with those three keys.
Rules:
  - Quantities must be integers
  - Prices must be rounded to 2 decimal places
  - If a field is missing, use null
"""


class InvoiceRequest(BaseModel):
    raw_text: str


class InvoiceResponse(BaseModel):
    vendor: str
    total_usd: float
    line_items: list[dict]


@app.post("/process", response_model=InvoiceResponse)
def process_invoice(req: InvoiceRequest):
    """
    Extract structured data from raw invoice text.

    First call:  AI generates an extraction plan (~500ms, ~$0.003)
    Every call after:  Pure Python, no AI (~2ms, $0.000)
    """
    result = runner.run_inline(
        name="invoice_extraction",
        task=EXTRACTION_TASK,
        inputs={"raw_text": req.raw_text},
    )

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)

    return InvoiceResponse(**result.output)
