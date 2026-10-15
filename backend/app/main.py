"""FastAPI application factory.

Run locally:  uv run uvicorn app.main:create_app --factory --reload
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.agent import Agent, FakeAgent
from app.config import Settings, get_settings
from app.db import make_engine, make_session_factory
from app.errors import install_error_handlers
from app.ratelimit import RateLimiter
from app.routers import health, sessions, watchlist

logger = logging.getLogger(__name__)


def build_agent(settings: Settings) -> Agent:
    if settings.agent_mode == "fake":
        return FakeAgent()

    missing = [
        name
        for name, value in (
            ("OPENAI_API_KEY", settings.openai_api_key),
            ("ALPHAVANTAGE_API_KEY", settings.alphavantage_api_key),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(f"AGENT_MODE=openai requires {', '.join(missing)} to be set")

    from app.agent.openai_agent import OpenAIAgent  # imported lazily: heavy and network-bound

    return OpenAIAgent(
        model=settings.openai_model,
        openai_api_key=settings.openai_api_key.get_secret_value(),  # type: ignore[union-attr]
        alphavantage_api_key=settings.alphavantage_api_key.get_secret_value(),  # type: ignore[union-attr]
        mcp_url=settings.alphavantage_mcp_url,
        tracing_enabled=settings.agent_tracing_enabled,
    )


def create_app(settings: Settings | None = None, agent: Agent | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        current = app.state.agent
        if hasattr(current, "start"):
            await current.start()
        try:
            yield
        finally:
            if hasattr(current, "stop"):
                await current.stop()
            app.state.engine.dispose()

    app = FastAPI(
        title="Stock Research Assistant API",
        version=__version__,
        lifespan=lifespan,
    )
    engine = make_engine(settings.database_url)
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    app.state.agent = agent or build_agent(settings)
    app.state.rate_limiter = RateLimiter(settings.rate_limit_per_minute)

    install_error_handlers(app)
    app.include_router(health.router)
    app.include_router(sessions.router)
    app.include_router(watchlist.router)
    logger.info("Started in %s agent mode", settings.agent_mode)
    return app
