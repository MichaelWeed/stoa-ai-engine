"""LiteLLM-backed planner client.

The AI is called exactly once per workflow — here — to produce a plan.
All subsequent work is deterministic code execution.
API keys are read ephemerally from the environment; they are never logged,
stored in the database, or passed to the model's context window.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import litellm
from litellm import completion

from stoa.config import get_config

# Suppress LiteLLM's verbose default logging
litellm.set_verbose = False


@dataclass
class CompletionResult:
    content: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: float
    model: str
    provider: str


class PlannerClient:
    """Thin wrapper around LiteLLM that enforces:
    - provider and model come from config, not call-site arguments
    - token usage is always returned for budget accounting
    - API keys are loaded from env and never persisted
    """

    def __init__(self) -> None:
        self._config = get_config()
        self._model_string = self._build_model_string()

    def _build_model_string(self) -> str:
        provider = self._config.provider.lower()
        model = self._config.model
        # LiteLLM routing: provider/model or just model for openai
        if provider == "openai":
            return model
        if provider == "anthropic":
            return f"anthropic/{model}"
        if provider == "google":
            return f"gemini/{model}"
        if provider == "ollama":
            return f"ollama/{model}"
        return model

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> CompletionResult:
        start = time.perf_counter()
        response = completion(
            model=self._model_string,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        latency_ms = (time.perf_counter() - start) * 1000

        usage = response.usage
        return CompletionResult(
            content=response.choices[0].message.content or "",
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            latency_ms=latency_ms,
            model=self._config.model,
            provider=self._config.provider,
        )

    @property
    def provider(self) -> str:
        return self._config.provider

    @property
    def model(self) -> str:
        return self._config.model
