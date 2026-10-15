import pytest

from app.db import make_engine


@pytest.mark.parametrize(
    "url",
    ["postgres://u:p@db:5432/app", "postgresql://u:p@db:5432/app"],
)
def test_provider_postgres_urls_use_psycopg3(url):
    # Hosting providers hand out postgres:// URLs; SQLAlchemy needs a driver name.
    engine = make_engine(url)  # no connection is made until first use
    assert engine.url.drivername == "postgresql+psycopg"
    assert engine.url.host == "db"
    engine.dispose()


def test_sqlite_enforces_foreign_keys():
    engine = make_engine("sqlite://")
    with engine.connect() as conn:
        assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
    engine.dispose()
