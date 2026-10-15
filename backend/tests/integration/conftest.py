"""Integration test setup: the real app, real HTTP, and a real database.

The database schema is built by the real Alembic migrations, so these tests
also prove the migrations work. By default a temporary SQLite file is used; set
TEST_DATABASE_URL to run against Postgres (CI does this):

    TEST_DATABASE_URL=postgresql://app:app@localhost:5432/app_test uv run pytest tests/integration
"""

import os
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.agent import Agent, FakeAgent
from app.config import Settings
from app.db import make_engine
from app.main import create_app

BACKEND_DIR = Path(__file__).resolve().parents[2]
TABLES = ("messages", "chat_sessions", "watchlist_items")  # children first


@pytest.fixture(scope="session")
def database_url(tmp_path_factory) -> str:
    url = os.environ.get("TEST_DATABASE_URL") or (
        f"sqlite:///{tmp_path_factory.mktemp('db') / 'test.db'}"
    )
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    config.attributes["database_url"] = url
    command.upgrade(config, "head")
    return url


@pytest.fixture(autouse=True)
def clean_database(database_url) -> Iterator[None]:
    yield
    engine = make_engine(database_url)
    with engine.begin() as conn:
        for table in TABLES:
            conn.execute(text(f"DELETE FROM {table}"))  # noqa: S608 (fixed table names)
    engine.dispose()


@pytest.fixture
def make_client(database_url) -> Iterator[Callable[..., TestClient]]:
    """Build a client. Optionally pass an agent; other keyword arguments override settings."""
    clients: list[TestClient] = []

    def _make(agent: Agent | None = None, **overrides) -> TestClient:
        settings = Settings(
            _env_file=None,
            database_url=database_url,
            agent_mode="fake",
            **({"rate_limit_per_minute": 1000} | overrides),
        )
        client = TestClient(create_app(settings, agent=agent or FakeAgent()))
        client.__enter__()  # runs the app's startup/shutdown (lifespan)
        clients.append(client)
        return client

    yield _make
    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture
def client(make_client) -> TestClient:
    return make_client()
