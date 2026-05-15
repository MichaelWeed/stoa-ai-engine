"""Budget enforcer — the circuit breaker that prevents runaway costs.

Every task run has three hard limits. If any is breached, BudgetExceeded
is raised and the run halts immediately. There is no retry. There is no
override at runtime. The only way to change these limits is to update
the config and restart.

Why this matters in plain English:
  A GPT-4o agent stuck in a loop, hitting a 128k context ceiling each
  iteration, costs ~$1.28 per loop. Twenty loops = $25.60. A weekend of
  unmonitored production = potentially thousands. The enforcer makes
  that impossible.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from stoa.config import get_config
from stoa.providers.pricing import tokens_to_usd


class BudgetExceeded(Exception):
    """Raised when a hard budget limit is breached. Halts the workflow."""


@dataclass
class BudgetSnapshot:
    steps_used: int
    steps_limit: int
    tokens_used: int
    tokens_limit: int
    elapsed_seconds: float
    timeout_seconds: int
    cost_usd: float

    @property
    def steps_remaining(self) -> int:
        return max(0, self.steps_limit - self.steps_used)

    @property
    def tokens_remaining(self) -> int:
        return max(0, self.tokens_limit - self.tokens_used)

    def as_dict(self) -> dict:
        return {
            "steps": f"{self.steps_used}/{self.steps_limit}",
            "tokens": f"{self.tokens_used:,}/{self.tokens_limit:,}",
            "elapsed": f"{self.elapsed_seconds:.1f}s / {self.timeout_seconds}s",
            "cost_usd": f"${self.cost_usd:.4f}",
        }


class BudgetEnforcer:
    """Tracks and enforces hard limits for one task run."""

    def __init__(self, model: str) -> None:
        cfg = get_config()
        self._max_steps = cfg.max_steps
        self._token_budget = cfg.token_budget
        self._timeout = cfg.step_timeout_seconds
        self._model = model

        self._steps = 0
        self._prompt_tokens = 0
        self._completion_tokens = 0
        self._start_time = time.monotonic()

    def record_step(self, prompt_tokens: int = 0, completion_tokens: int = 0) -> None:
        """Call once per workflow step. Raises BudgetExceeded if any limit is hit."""
        self._steps += 1
        self._prompt_tokens += prompt_tokens
        self._completion_tokens += completion_tokens

        total_tokens = self._prompt_tokens + self._completion_tokens
        elapsed = time.monotonic() - self._start_time

        if self._steps > self._max_steps:
            raise BudgetExceeded(
                f"Step limit reached: {self._steps} steps (limit: {self._max_steps}). "
                f"Workflow halted. Increase STOA_MAX_STEPS in .env if this is intentional."
            )

        if total_tokens > self._token_budget:
            cost = tokens_to_usd(self._model, self._prompt_tokens, self._completion_tokens)
            raise BudgetExceeded(
                f"Token budget reached: {total_tokens:,} tokens used "
                f"(limit: {self._token_budget:,}, cost so far: ${cost:.4f}). "
                f"Workflow halted. Increase STOA_TOKEN_BUDGET in .env if this is intentional."
            )

        if elapsed > self._timeout * self._steps:
            raise BudgetExceeded(
                f"Time budget exceeded: {elapsed:.1f}s elapsed for {self._steps} steps "
                f"(per-step limit: {self._timeout}s). Workflow halted."
            )

    def snapshot(self) -> BudgetSnapshot:
        total_tokens = self._prompt_tokens + self._completion_tokens
        return BudgetSnapshot(
            steps_used=self._steps,
            steps_limit=self._max_steps,
            tokens_used=total_tokens,
            tokens_limit=self._token_budget,
            elapsed_seconds=time.monotonic() - self._start_time,
            timeout_seconds=self._timeout,
            cost_usd=tokens_to_usd(self._model, self._prompt_tokens, self._completion_tokens),
        )
