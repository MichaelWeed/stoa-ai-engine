# Example: API Extraction with Schema-Drift Recovery

## What it does

Fetches data from a REST API and extracts structured fields. If the API
changes its format, Stoa detects the failure, fixes the extraction code
automatically, and records the fix so it never needs fixing again.

## Why this matters

Third-party APIs change. A field gets renamed. A nested object gets flattened.
A new required parameter appears. With a standard AI agent, the whole workflow
crashes. A developer gets paged. The fix is a 10-minute job — but it interrupts
whoever is on call.

Stoa's Reflexion engine handles this automatically:
1. The extraction step fails with a KeyError or JSONDecodeError
2. Stoa classifies this as a structural failure (not a transient one)
3. It calls the AI once more — not to redo the whole workflow, but just to fix
   the broken extraction step
4. The fix is validated and tested in the sandbox
5. Execution resumes
6. The fix is written to learnings.md — future runs see the fix immediately

## Run it

```bash
stoa run examples/api_extraction/workflow.yaml
```

## To simulate schema drift

Edit `workflow.yaml` and change `api_url` to a URL that returns a slightly
different format. Stoa will catch the failure, repair it, and log the fix.

## What the compiled plan looks like

```python
# Step 1: tool_call — http_get fetches the data (authorized by policy)
# data = INPUTS["_tool_result_http_get"]

items = data[:5]
result = [
    {"id": item["id"], "title": item["title"], "body": item["body"]}
    for item in items
]
```

If the API changes `"title"` to `"subject"`, the KeyError is caught, and
Stoa rewrites `item["title"]` to `item["subject"]` automatically.
