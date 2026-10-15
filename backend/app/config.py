"""Application settings, read from environment variables (and `.env` in development)."""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
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
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
