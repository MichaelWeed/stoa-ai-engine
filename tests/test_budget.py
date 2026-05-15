"""Tests for the budget enforcer (circuit breaker)."""

import pytest
from stoa.budget.enforcer import BudgetEnforcer, BudgetExceeded
from stoa.config import StoaConfig
from unittest.mock import patch


def _tight_enforcer(max_steps: int = 3, token_budget: int = 100) -> BudgetEnforcer:
    cfg = StoaConfig(
        STOA_MAX_STEPS=max_steps,
        STOA_TOKEN_BUDGET=token_budget,
        STOA_STEP_TIMEOUT_SECONDS=9999,
    )
    with patch("stoa.budget.enforcer.get_config", return_value=cfg):
        return BudgetEnforcer(model="gpt-4o-mini")


def test_step_limit_enforced():
    enforcer = _tight_enforcer(max_steps=2)
    enforcer.record_step()
    enforcer.record_step()
    with pytest.raises(BudgetExceeded, match="Step limit"):
        enforcer.record_step()


def test_token_limit_enforced():
    enforcer = _tight_enforcer(token_budget=50)
    with pytest.raises(BudgetExceeded, match="Token budget"):
        enforcer.record_step(prompt_tokens=30, completion_tokens=30)


def test_snapshot_reflects_usage():
    enforcer = _tight_enforcer(max_steps=10, token_budget=10000)
    enforcer.record_step(prompt_tokens=100, completion_tokens=50)
    snap = enforcer.snapshot()
    assert snap.steps_used == 1
    assert snap.tokens_used == 150
    assert snap.steps_remaining == 9


def test_no_breach_within_limits():
    enforcer = _tight_enforcer(max_steps=5, token_budget=10000)
    for _ in range(5):
        enforcer.record_step(prompt_tokens=10, completion_tokens=5)
    # Should not raise — we hit the limit exactly on step 5 but haven't exceeded it
    snap = enforcer.snapshot()
    assert snap.steps_used == 5
