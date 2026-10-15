import pytest
from sqlalchemy.orm import Session

from app import models  # noqa: F401  (registers tables)
from app.db import Base, make_engine, make_session_factory


@pytest.fixture
def db() -> Session:
    """A fresh in-memory SQLite database per test (schema from the models)."""
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    with make_session_factory(engine)() as session:
        yield session
    engine.dispose()
