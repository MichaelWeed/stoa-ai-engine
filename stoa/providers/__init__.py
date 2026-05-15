"""Provider abstraction — swap AI vendors via config, not code changes."""

from stoa.providers.client import PlannerClient, CompletionResult

__all__ = ["PlannerClient", "CompletionResult"]
