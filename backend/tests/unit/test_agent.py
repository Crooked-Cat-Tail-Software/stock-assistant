from types import SimpleNamespace

import anyio
import pytest

from app.agent import AgentError, FakeAgent, HistoryItem
from app.agent.fake import FAIL_TRIGGER
from app.agent.openai_agent import _tool_call
from app.config import Settings
from app.main import build_agent


def run(coro_fn, *args):
    return anyio.run(coro_fn, *args)


def test_fake_agent_uses_quote_tool_for_tickers():
    reply = run(FakeAgent().reply, [], "What is AAPL's latest price?")
    assert reply.tool_calls == [{"name": "GLOBAL_QUOTE", "arguments": {"symbol": "AAPL"}}]
    assert "AAPL" in reply.content


def test_fake_agent_sees_history():
    history = [HistoryItem("user", "hi"), HistoryItem("assistant", "hello")]
    reply = run(FakeAgent().reply, history, "and now?")
    assert "2 earlier messages" in reply.content
    assert reply.tool_calls == []


def test_fake_agent_can_simulate_failure():
    with pytest.raises(AgentError):
        run(FakeAgent().reply, [], f"please {FAIL_TRIGGER}")


def test_tool_call_parses_json_arguments():
    item = SimpleNamespace(
        raw_item=SimpleNamespace(name="GLOBAL_QUOTE", arguments='{"symbol":"X"}')
    )
    assert _tool_call(item) == {"name": "GLOBAL_QUOTE", "arguments": {"symbol": "X"}}


def test_tool_call_keeps_unparseable_arguments():
    item = SimpleNamespace(raw_item=SimpleNamespace(name="T", arguments="not json"))
    assert _tool_call(item) == {"name": "T", "arguments": {"raw": "not json"}}


def test_openai_mode_requires_both_keys():
    settings = Settings(_env_file=None, agent_mode="openai", openai_api_key="sk-test")
    with pytest.raises(RuntimeError, match="ALPHAVANTAGE_API_KEY"):
        build_agent(settings)


def test_fake_mode_needs_no_keys():
    assert isinstance(build_agent(Settings(_env_file=None, agent_mode="fake")), FakeAgent)
