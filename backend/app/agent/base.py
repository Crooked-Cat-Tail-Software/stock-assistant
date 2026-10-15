"""The interface every agent implementation follows.

Routes and services depend only on this, so tests can swap in `FakeAgent`
without touching OpenAI or Alpha Vantage.
"""

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol


@dataclass(frozen=True)
class HistoryItem:
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True)
class AgentReply:
    content: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


class AgentError(Exception):
    """The model or market-data service failed. The message is safe to show users."""


class Agent(Protocol):
    async def reply(self, history: list[HistoryItem], question: str) -> AgentReply: ...
