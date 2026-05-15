"""Central configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

load_dotenv()


class StoaConfig(BaseSettings):
    # Provider
    provider: str = Field(default="openai", alias="STOA_PROVIDER")
    model: str = Field(default="gpt-4o", alias="STOA_MODEL")

    # Budget hard limits
    max_steps: int = Field(default=25, alias="STOA_MAX_STEPS")
    token_budget: int = Field(default=50_000, alias="STOA_TOKEN_BUDGET")
    step_timeout_seconds: int = Field(default=30, alias="STOA_STEP_TIMEOUT_SECONDS")

    # Sandbox
    sandbox: str = Field(default="docker", alias="STOA_SANDBOX")
    sandbox_timeout_seconds: int = Field(default=60, alias="STOA_SANDBOX_TIMEOUT_SECONDS")
    sandbox_memory_mb: int = Field(default=256, alias="STOA_SANDBOX_MEMORY_MB")

    # Storage
    db_url: str = Field(
        default="sqlite+aiosqlite:///stoa.db", alias="STOA_DB_URL"
    )

    # API server
    api_host: str = Field(default="127.0.0.1", alias="STOA_API_HOST")
    api_port: int = Field(default=8000, alias="STOA_API_PORT")

    model_config = {"populate_by_name": True, "extra": "ignore"}


@lru_cache(maxsize=1)
def get_config() -> StoaConfig:
    return StoaConfig()
