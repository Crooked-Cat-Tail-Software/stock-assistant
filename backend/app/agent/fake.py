"""Deterministic stand-in for the real agent: no network, no API keys.

Used by tests, CI, and `AGENT_MODE=fake` demos.
"""

import re

from app.agent.base import AgentError, AgentReply, HistoryItem

_TICKER = re.compile(r"\b[A-Z]{1,5}\b")
FAIL_TRIGGER = "__fail__"


class FakeAgent:
    async def reply(self, history: list[HistoryItem], question: str) -> AgentReply:
        if FAIL_TRIGGER in question:
            raise AgentError("The market data service is unavailable. Please try again later.")

        tickers = [t for t in _TICKER.findall(question) if t not in {"I", "A"}]
        if not tickers:
            return AgentReply(
                content=f"(fake agent) You asked: {question!r}. "
                f"This session has {len(history)} earlier messages."
            )

        symbol = tickers[0]
        return AgentReply(
            content=f"(fake agent) {symbol} last traded at $123.45. "
            "This is sample data, not investment advice.",
            tool_calls=[{"name": "GLOBAL_QUOTE", "arguments": {"symbol": symbol}}],
        )
