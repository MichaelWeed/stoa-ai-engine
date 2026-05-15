# Incorporating Stoa — A Developer Walkthrough

The fastest way to understand Stoa is to see a before and after.

This walkthrough uses a small invoice processing API — a problem every developer
has touched in some form. The specific domain doesn't matter. The pattern does.

> **Default model: `gpt-4o`.** Stoa is model-agnostic — swap to Claude (Anthropic),
> Gemini (Google), or a local model by changing one environment variable.
> But we default to GPT-4o because it is the model most teams are already
> paying too much for, and that is exactly what Stoa is built to fix.

---

## The Example

A FastAPI endpoint receives raw invoice text and returns structured JSON:
vendor name, total amount, and a list of line items.

```
POST /process
{"raw_text": "Acme Corp\nWidget x3 @ $25.00 each\nShipping: $9.99\nTotal: $84.99"}

→ {"vendor": "Acme Corp", "total_usd": 84.99, "line_items": [...]}
```

Two working implementations live in this repo:

| Directory | Description |
|---|---|
| [`examples/invoice_api/`](invoice_api/) | Standard approach — OpenAI called on every request |
| [`examples/invoice_api_with_stoa/`](invoice_api_with_stoa/) | Stoa approach — OpenAI called once, code runs forever |

---

## What Changes When You Add Stoa

Open both `main.py` files side by side. The FastAPI routes, the Pydantic models,
and the response shape are identical. The only difference is how the extraction runs.

### Before (standard OpenAI usage)

```python
# Every request ships tokens to OpenAI.
# 10,000 invoices/day = 10,000 API calls. The bill scales linearly with your success.
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": prompt}],
    response_format={"type": "json_object"},
)
```

### After (with Stoa)

```python
# OpenAI is called once to generate the extraction logic.
# After that, the logic runs as plain Python — no API, no tokens, no bill.
result = runner.run_inline(
    name="invoice_extraction",
    task=EXTRACTION_TASK,
    inputs={"raw_text": req.raw_text},
)
```

That's the entire integration. One import, one runner, one call.

---

## What Stoa Does Behind That Call

**First request** — OpenAI earns its fee exactly once:

```
1. Stoa receives the task description
2. It sends a single planning prompt to GPT-4o
3. GPT-4o returns a Python extraction function
4. Stoa validates the code (AST safety check — no file writes, no network calls)
5. It runs the code in a sandbox with your inputs
6. It caches the plan under an idempotency key
7. It returns your structured data
```

**Every subsequent request** — OpenAI is not involved:

```
1. Stoa checks the cache — hit
2. It runs the cached Python code directly
3. Returns in ~2ms, $0.00 in OpenAI tokens
```

GPT-4o wrote the code. It doesn't need to re-read the invoice to run it.

---

## The Cost Reality

Running the standard version at modest scale against GPT-4o (`gpt-4o` input: $2.50/1M tokens):

| Volume | Without Stoa | With Stoa | Savings |
|---|---|---|---|
| 100 invoices/day | ~$0.18 | ~$0.003 (first run only) | 98% |
| 10,000 invoices/day | ~$18.00 | ~$0.003 | >99% |
| 1,000,000 invoices/day | ~$1,800.00 | ~$0.003 | >99% |

The Stoa cost is flat. It does not scale with volume. OpenAI's does.

> **Model flexibility**: Replace `gpt-4o` with `claude-3-5-sonnet`, `gemini-1.5-pro`,
> or any LiteLLM-compatible endpoint by setting `STOA_MODEL` in your environment.
> The planning cost changes. The zero-cost execution after that does not.

---

## Why This Matters For Your App

Think about wherever your app is calling OpenAI right now. Ask yourself:

- **Is the task structurally the same each time, just with different data?**
  → That's the Stoa pattern. The logic is constant; only the input changes.
  → You are paying OpenAI to do the same reasoning on every request.

- **Does the output need to be consistent, not just "probably right"?**
  → GPT-4o's output varies subtly across identical prompts. Stoa's cached code does not.

- **Are you worried about runaway costs if a queue backs up?**
  → Stoa's budget enforcer caps steps and tokens per run before execution starts.
  → A stuck queue doesn't become a $4,000 OpenAI invoice overnight.

Common patterns where the swap is immediate:

| Your app does this with OpenAI today | Stoa eliminates this |
|---|---|
| Parses incoming emails for intent | Token spend per email |
| Extracts entities from support tickets | Cost that scales with ticket volume |
| Scores documents against a rubric | Subtle variance across identical inputs |
| Validates a form against business rules | Probabilistic pass/fail on deterministic logic |
| Summarizes structured reports | Full model invocation for templated output |

---

## Running the Examples

**Without Stoa** — every curl costs tokens:
```bash
cd examples/invoice_api
pip install -r requirements.txt
OPENAI_API_KEY=sk-... uvicorn main:app --reload
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{"raw_text": "Acme Corp\nWidget x3 @ $25 each\nTotal: $75"}'
```

**With Stoa** — first curl costs tokens. Every curl after that does not:
```bash
cd examples/invoice_api_with_stoa
pip install -r requirements.txt
OPENAI_API_KEY=sk-... uvicorn main:app --reload
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{"raw_text": "Acme Corp\nWidget x3 @ $25 each\nTotal: $75"}'

# Run it again. Same result. Zero new tokens sent to OpenAI.
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{"raw_text": "Globex Inc\nConsulting x10hrs @ $150\nTotal: $1500"}'
```

The response is identical in structure. Your token counter didn't move on the second call.

---

## Next Steps

Once you see the pattern, the natural next question is: what else can I stop paying OpenAI per-call for?

Stoa ships with a [policy system](../policies/) for controlling exactly what the
generated code is allowed to do, and a [budget enforcer](../stoa/budget/) for
capping the one-time planning cost at the workflow level. Both are a single YAML file.

The [ROADMAP](../ROADMAP.md) covers what's coming, including a persistent plan
store so generated code survives service restarts — meaning the planning call
happens once per deployment, not once per process.
