"""Application settings, read from environment variables (and `.env` in development)."""

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    database_url: str = "sqlite:///./dev.db"

    # "openai" runs the real agent; "fake" returns canned replies (tests, CI, demos without keys)
    agent_mode: Literal["openai", "fake"] = "fake"
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-4.1-mini"
    alphavantage_api_key: SecretStr | None = None
    alphavantage_mcp_url: str = "https://mcp.alphavantage.co/mcp"
    # The Agents SDK uploads run traces (including message content) to OpenAI unless disabled.
    agent_tracing_enabled: bool = False

    rate_limit_per_minute: int = 10
    # Shared secret between the frontend's nginx and the backend. When set, /api/*
    # requests (except /api/health) must carry it in X-Internal-Token. Used where
    # the backend is publicly reachable (Render); unset in Compose and local dev.
    internal_api_token: SecretStr | None = None
    # Commit being run. Render sets RENDER_GIT_COMMIT automatically.
    git_commit: str | None = Field(
        default=None, validation_alias=AliasChoices("GIT_COMMIT", "RENDER_GIT_COMMIT")
    )
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
