"""Reflexion engine — automatic repair of broken workflow steps.

When a step fails, the engine:
  1. Classifies the failure (transient vs. structural)
  2. For transient failures (timeouts, rate limits): exponential backoff + retry
  3. For structural failures (schema drift, JSON parse errors): calls the AI
     once more with the error context to rewrite just the broken step
  4. Validates the rewritten step before re-executing
  5. Records the fix in the learnings ledger

The AI is only called again if the failure is structural and a code fix
is needed. Transient failures are handled entirely by deterministic retry
logic — no AI involvement.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any


class FailureType(str, Enum):
    TRANSIENT = "transient"   # network timeout, rate limit — retry with backoff
    STRUCTURAL = "structural"  # schema drift, JSON parse error — needs AI repair
    BUDGET = "budget"          # budget exceeded — cannot recover
    SECURITY = "security"      # policy violation — do not recover


@dataclass
class FailureSignature:
    step_id: str
    error_message: str
    failure_type: FailureType
    context: dict[str, Any]


_TRANSIENT_PATTERNS = [
    "timeout", "timed out", "rate limit", "rate_limit",
    "429", "503", "502", "connection", "network",
]

_STRUCTURAL_PATTERNS = [
    "json", "parse", "schema", "key error", "keyerror",
    "attribute", "index", "decode", "unexpected",
]


def classify_failure(error: str) -> FailureType:
    lower = error.lower()
    if any(p in lower for p in _TRANSIENT_PATTERNS):
        return FailureType.TRANSIENT
    if any(p in lower for p in _STRUCTURAL_PATTERNS):
        return FailureType.STRUCTURAL
    return FailureType.STRUCTURAL  # default: attempt structural repair


class ReflexionEngine:
    """Wraps step execution with failure detection and automatic repair."""

    MAX_TRANSIENT_RETRIES = 3
    BASE_BACKOFF_SECONDS = 1.0

    def __init__(self, planner_client: Any, validator: Any, ledger: Any) -> None:
        self._client = planner_client
        self._validator = validator
        self._ledger = ledger

    def classify(self, error: str) -> FailureType:
        return classify_failure(error)

    def retry_transient(self, fn: Any, step_id: str, max_retries: int | None = None) -> Any:
        """Retry a function with exponential backoff for transient failures."""
        retries = max_retries or self.MAX_TRANSIENT_RETRIES
        for attempt in range(retries):
            try:
                return fn()
            except Exception as exc:
                if classify_failure(str(exc)) != FailureType.TRANSIENT:
                    raise
                if attempt == retries - 1:
                    raise
                wait = self.BASE_BACKOFF_SECONDS * (2 ** attempt)
                time.sleep(wait)
        raise RuntimeError("Unreachable")

    def repair_structural(
        self,
        workflow_name: str,
        step_id: str,
        broken_code: str,
        error: str,
        context: dict[str, Any],
    ) -> str:
        """Ask the AI to rewrite a broken step. Validate the result before returning."""
        from stoa.compiler.validator import ASTValidator

        repair_prompt = (
            f"A workflow step failed with this error:\n\n"
            f"```\n{error}\n```\n\n"
            f"The broken code was:\n\n"
            f"```python\n{broken_code}\n```\n\n"
            f"Context available: {context}\n\n"
            f"Rewrite ONLY the broken code to fix the error. "
            f"Return only the fixed Python code, no explanation."
        )

        result = self._client.complete(
            system_prompt=(
                "You are a code repair specialist. Fix broken Python code. "
                "Return only valid Python. No markdown, no explanation."
            ),
            user_prompt=repair_prompt,
            temperature=0.0,
        )

        fixed_code = result.content.strip()
        # Strip markdown fences if the model added them anyway
        if fixed_code.startswith("```"):
            lines = fixed_code.split("\n")
            fixed_code = "\n".join(lines[1:-1])

        ASTValidator().validate_or_raise(fixed_code)

        self._ledger.record(
            workflow=workflow_name,
            step_id=step_id,
            failure=error[:200],
            fix=f"Code rewritten. First line: {fixed_code.split(chr(10))[0][:100]}",
        )

        return fixed_code
