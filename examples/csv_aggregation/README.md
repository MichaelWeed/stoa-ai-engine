# Example: CSV Aggregation

## What it does

Reads a CSV file and computes totals, averages, and rankings — with exact,
reproducible results every time.

## Why this matters

Ask a language model to sum a column. It will usually get it right. Ask it
to sum 10,000 rows, or ask it again in a different session, and you may get
different answers. This is not a bug — it is how language models work. They
are statistical text predictors, not calculators.

Stoa solves this by having the AI write the calculation as Python code once.
Python then executes the code. Python's arithmetic is exact and deterministic.
The AI never touches the numbers again.

## Run it

```bash
stoa run examples/csv_aggregation/workflow.yaml
```

Expected output:
```
✓ Completed  3 steps  10,432 tokens  $0.0142
```

Run it 100 more times. The token count stays at 0 for every run after the first.
The output is identical every time.

## What the compiled plan looks like

The AI produces a plan with a compute step like this:

```python
import csv

with open(INPUTS["csv_path"]) as f:
    rows = list(csv.DictReader(f))

amounts = [float(r["amount"]) for r in rows]
total = sum(amounts)
average = round(total / len(amounts), 2)
top_3 = sorted(rows, key=lambda r: float(r["amount"]), reverse=True)[:3]

result = {
    "total": total,
    "average": average,
    "row_count": len(rows),
    "top_3": [{"name": r["name"], "amount": float(r["amount"])} for r in top_3],
}
```

This code is validated by the AST checker (no `eval`, no shell calls, no
network access), then executed in an isolated sandbox. The sandbox has no
access to anything except the input file you gave it.
