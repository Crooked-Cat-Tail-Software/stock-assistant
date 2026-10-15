"""Alembic migration environment. Uses DATABASE_URL, same as the app."""

from logging.config import fileConfig

from alembic import context

from app import models  # noqa: F401  (registers the tables on Base.metadata)
from app.config import get_settings
from app.db import Base, make_engine

config = context.config
if config.config_file_name is not None:
    # Keep loggers that already exist (e.g. the app's, when migrations run
    # in-process from tests). The default would silently disable them.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations() -> None:
    url = config.attributes.get("database_url") or get_settings().database_url
    engine = make_engine(url)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=connection.dialect.name == "sqlite",
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


run_migrations()
