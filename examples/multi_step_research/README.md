# Example: Multi-Step Research with Budget Enforcement

## What it does

A three-step workflow: fetch content → extract facts → write summary.
Demonstrates budget circuit breakers and the policy gateway working together.

## Why this matters

Multi-step workflows are where AI agents fail most expensively. Each step
can fail independently. A stuck step can loop indefinitely. The AI might
try to call a tool it isn't authorized to use. Without guardrails, one bad
run can cost hundreds of dollars.

With Stoa:
- Each step is logged against the budget before it runs
- If the total steps, tokens, or time exceeds the configured limit, the
  workflow halts immediately and returns a clean error
- Tool calls are pre-authorized before execution — a step cannot call
  a tool that isn't on the policy allow list
- The FSM ensures steps execute in order: planning → executing → verifying.
  The workflow cannot jump states or skip the verification gate.

## Run it

```bash
stoa run examples/multi_step_research/workflow.yaml
```

## To see the circuit breaker in action

Add these overrides to your `.env` to set a very tight limit:

```
STOA_MAX_STEPS=2
```

Then run again. Stoa will halt after 2 steps and return:

```
✗ Failed: Step limit reached: 3 steps (limit: 2). Workflow halted.
  Increase STOA_MAX_STEPS in .env if this is intentional.
```

This is the behavior that prevents a $200 bill at 3am. The error is clean,
structured, and handleable in code — not a silent runaway process.

## FSM trace

Every run produces a trace you can inspect:

```json
[
  {"from": "pending",   "to": "planning",   "reason": "starting planning"},
  {"from": "planning",  "to": "executing",  "reason": "plan validated"},
  {"from": "executing", "to": "verifying",  "reason": "all steps completed"},
  {"from": "verifying", "to": "complete",   "reason": "output verified"}
]
```

If a step fails and recovers:

```json
[
  ...
  {"from": "executing",  "to": "recovering", "reason": "step extract failed: KeyError 'body'"},
  {"from": "recovering", "to": "executing",  "reason": "step extract recovered"},
  ...
]
```
