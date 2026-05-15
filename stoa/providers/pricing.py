"""Token-to-USD pricing for cost accounting.

Prices are per 1M tokens at list price as of May 2026.
These are used for reporting and the savings calculator — not billing.
Update when providers change pricing.
"""

from __future__ import annotations

# (input_price_per_1m, output_price_per_1m)
_PRICES: dict[str, tuple[float, float]] = {
    # OpenAI
    "gpt-4o": (5.00, 15.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.00, 30.00),
    "o3": (10.00, 40.00),
    "o4-mini": (1.10, 4.40),
    # Anthropic
    "claude-opus-4-7": (15.00, 75.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-haiku-4-5-20251001": (0.80, 4.00),
    # Google
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-2.5-flash": (0.15, 0.60),
}

_DEFAULT_PRICE = (5.00, 15.00)  # fallback — assume GPT-4o pricing

# Real-world adjustment: theoretical savings are reduced by roughly 15% because:
#   - Schema drift recovery triggers an additional AI call (~5% of runs)
#   - Some tasks in any workflow mix are one-offs, not repeated (~5%)
#   - Occasional re-planning when task requirements change (~5%)
REAL_WORLD_HAIRCUT = 0.15


def tokens_to_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    input_price, output_price = _PRICES.get(model, _DEFAULT_PRICE)
    return (prompt_tokens / 1_000_000 * input_price) + (
        completion_tokens / 1_000_000 * output_price
    )


def cost_formula(model: str, prompt_tokens: int, completion_tokens: int) -> dict:
    """Return the formula components so callers can show their work."""
    input_price, output_price = _PRICES.get(model, _DEFAULT_PRICE)
    cost_per_run = tokens_to_usd(model, prompt_tokens, completion_tokens)
    return {
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "input_price_per_1m": input_price,
        "output_price_per_1m": output_price,
        "formula": (
            f"({prompt_tokens:,} / 1,000,000 × ${input_price}) "
            f"+ ({completion_tokens:,} / 1,000,000 × ${output_price})"
        ),
        "cost_per_run_usd": round(cost_per_run, 6),
    }


def savings_at_n_runs(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    n_runs: int,
    apply_haircut: bool = True,
) -> dict:
    """
    Theoretical savings formula:
      cost_without = cost_per_run × n_runs
      cost_with    = cost_per_run × 1         (one planning call; execution is free)
      savings      = cost_without - cost_with
      savings_pct  = (n_runs - 1) / n_runs

    Real-world adjustment (apply_haircut=True):
      Reduces theoretical savings by 15% to account for recovery AI calls,
      one-off tasks, and re-planning. A good-faith estimate, not a guarantee.
    """
    cost_per_run = tokens_to_usd(model, prompt_tokens, completion_tokens)
    cost_without = cost_per_run * n_runs
    cost_with_theoretical = cost_per_run  # one planning call

    theoretical_savings = cost_without - cost_with_theoretical
    theoretical_pct = (n_runs - 1) / n_runs * 100 if n_runs > 0 else 0

    if apply_haircut:
        actual_savings = theoretical_savings * (1 - REAL_WORLD_HAIRCUT)
        actual_pct = theoretical_pct * (1 - REAL_WORLD_HAIRCUT)
    else:
        actual_savings = theoretical_savings
        actual_pct = theoretical_pct

    return {
        "n_runs": n_runs,
        "cost_per_run_usd": round(cost_per_run, 6),
        "cost_without_stoa_usd": round(cost_without, 4),
        "cost_with_stoa_usd": round(cost_with_theoretical, 4),
        "theoretical_savings_usd": round(theoretical_savings, 4),
        "theoretical_savings_pct": round(theoretical_pct, 1),
        "real_world_savings_usd": round(actual_savings, 4),
        "real_world_savings_pct": round(actual_pct, 1),
        "haircut_applied_pct": REAL_WORLD_HAIRCUT * 100,
    }
