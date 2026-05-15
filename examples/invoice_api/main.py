"""
Invoice Processor — without Stoa

A standard FastAPI endpoint that calls an LLM to extract line items
from raw invoice text. This is the baseline most teams start with.

Problems this version has:
  - Every request hits the LLM. 1,000 invoices = 1,000 API calls.
  - Output is probabilistic. Two identical invoices may return
    slightly different structure.
  - No budget protection. A malformed invoice in a loop will
    keep calling the LLM until you notice the bill.
  - If the LLM is down, the endpoint is down.
"""

import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import OpenAI

app = FastAPI(title="Invoice Processor (without Stoa)")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


class InvoiceRequest(BaseModel):
    raw_text: str


class InvoiceResponse(BaseModel):
    vendor: str
    total_usd: float
    line_items: list[dict]


@app.post("/process", response_model=InvoiceResponse)
def process_invoice(req: InvoiceRequest):
    """Extract structured data from raw invoice text."""
    prompt = f"""
    Extract the following from this invoice and return valid JSON:
    - vendor (string)
    - total_usd (float)
    - line_items (list of {{description, quantity, unit_price_usd}})

    Invoice:
    {req.raw_text}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        data = response.choices[0].message.content
        import json
        return InvoiceResponse(**json.loads(data))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
