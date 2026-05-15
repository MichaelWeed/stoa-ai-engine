# Contributing to Stoa

Stoa is MIT licensed and welcomes contributions. This document covers the
ground rules that keep the codebase safe and the architecture coherent.

---

## Core principles (please read before submitting a PR)

**1. The AI is never in the execution loop.**
The entire value of Stoa comes from separating planning (AI) from execution
(deterministic code). Do not add code paths where the AI is called during
execution of a compiled plan. If you need a feature that requires runtime AI
inference, open an issue first to discuss the design.

**2. Deny-first security.**
The policy gateway defaults to deny. The sandbox defaults to no-network.
The AST validator defaults to reject unknown patterns. New features should
follow the same default-deny principle. Never add an "allow all" escape hatch.

**3. Real numbers, not estimates.**
If you change the execution path in a way that affects cost or latency, run
`make bench` before and after and include the diff in your PR.

---

## Getting started

```bash
git clone https://github.com/MichaelWeed/stoa
cd stoa
pip install -e ".[dev]"
cp .env.example .env
# Add your API key to .env
pytest
```

---

## What makes a good contribution

**Good PRs:**
- Add a new built-in tool to the tool registry (with a policy rule and tests)
- Add a new example workflow in `examples/`
- Improve the AST validator to catch additional unsafe patterns
- Add a new benchmark workflow to `benchmarks/`
- Fix a real bug (with a test that reproduces it)

**Needs design discussion first:**
- Changes to the FSM state machine (adding states, changing transitions)
- Changes to the budget enforcement logic
- New sandbox backends
- Anything that touches the policy gateway's core authorization logic

---

## Testing

All PRs must pass the test suite:

```bash
pytest --cov=stoa
```

For PRs that change execution behavior, also run:

```bash
make bench
```

And include the before/after summary in the PR description.

---

## Code style

```bash
ruff check .
mypy stoa/
```

Both must pass clean. The CI pipeline enforces this.
