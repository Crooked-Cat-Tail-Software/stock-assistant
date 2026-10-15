"""The real agent, with the OpenAI Agents SDK's Runner replaced (no network)."""

import logging
from types import SimpleNamespace

import anyio
import pytest
from agents.items import ToolCallItem

from app.agent import AgentError, HistoryItem
from app.agent import openai_agent as module
from app.agent.openai_agent import OpenAIAgent

SECRET = "AV-SECRET-KEY-123"  # noqa: S105 (dummy value the test checks for leaks)


@pytest.fixture
def agent() -> OpenAIAgent:
    # Constructing the agent does not open any network connection.
    return OpenAIAgent(
        model="gpt-test",
        openai_api_key="sk-test",
        alphavantage_api_key=SECRET,
        mcp_url="https://mcp.example.test/mcp",
    )


def fake_tool_call(name: str, arguments: str) -> ToolCallItem:
    item = ToolCallItem.__new__(ToolCallItem)
    item.raw_item = SimpleNamespace(name=name, arguments=arguments)
    return item


def test_reply_sends_history_then_question_and_collects_tool_calls(agent, monkeypatch):
    seen = {}

    async def fake_run(sdk_agent, run_input, **kwargs):
        seen["input"] = run_input
        return SimpleNamespace(
            final_output="AAPL is $1.",
            new_items=[fake_tool_call("GLOBAL_QUOTE", '{"symbol": "AAPL"}'), object()],
        )

    monkeypatch.setattr(module.Runner, "run", fake_run)
    history = [HistoryItem("user", "hi"), HistoryItem("assistant", "hello")]

    reply = anyio.run(agent.reply, history, "What is AAPL?")

    assert seen["input"] == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
        {"role": "user", "content": "What is AAPL?"},
    ]
    assert reply.content == "AAPL is $1."
    assert reply.tool_calls == [{"name": "GLOBAL_QUOTE", "arguments": {"symbol": "AAPL"}}]


def test_failures_become_agent_errors_without_leaking_the_api_key(agent, monkeypatch, caplog):
    async def failing_run(*args, **kwargs):
        # HTTP client errors typically include the full request URL.
        raise ConnectionError(f"failed: https://mcp.example.test/mcp?apikey={SECRET}")

    monkeypatch.setattr(module.Runner, "run", failing_run)

    with caplog.at_level(logging.DEBUG), pytest.raises(AgentError) as exc:
        anyio.run(agent.reply, [], "What is AAPL?")

    assert SECRET not in str(exc.value)
    assert SECRET not in caplog.text
    assert "ConnectionError" in caplog.text


def test_httpx_request_logging_is_silenced(agent):
    # httpx logs full URLs (including ?apikey=) at INFO level.
    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING


def test_agent_only_uses_the_alpha_vantage_mcp_server(agent):
    servers = agent._agent.mcp_servers
    assert [s.name for s in servers] == ["alphavantage"]
