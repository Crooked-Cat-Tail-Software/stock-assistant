"""FastAPI dependencies. Tests override these through `app.state`."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.agent import Agent
from app.errors import ApiError


def get_db(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


def get_agent(request: Request) -> Agent:
    return request.app.state.agent


def enforce_rate_limit(request: Request) -> None:
    client = request.client.host if request.client else "unknown"
    retry_after = request.app.state.rate_limiter.check(client)
    if retry_after is not None:
        raise ApiError(
            429,
            "rate_limited",
            f"Too many questions. Try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )


DbSession = Annotated[Session, Depends(get_db)]
AgentDep = Annotated[Agent, Depends(get_agent)]
