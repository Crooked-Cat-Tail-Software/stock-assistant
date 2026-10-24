"""Real agent: OpenAI Agents SDK + the Alpha Vantage MCP server.

Adapted from the Alpha Vantage MCP agent example (MIT license, see
THIRD_PARTY_NOTICES.md). Changes from the example:

- Connects only to the Alpha Vantage MCP server. The example's `filesystem`
  server is removed because it would let a prompt read files on the server.
- Adds read-only yfinance tools for quotes and price history (issue #19), so
  most questions don't use Alpha Vantage's free quota.
- One MCP connection is opened when the app starts and shared by all requests,
  instead of being tied to one terminal session.
- Conversation history comes from our own database rather than `SQLiteSession`.
- Runs to completion and returns the reply plus the tools used, instead of
  streaming to a terminal.
"""

import json
import logging
from typing import Any

from agents import Agent as SdkAgent
from agents import Runner, set_default_openai_key, set_tracing_disabled
from agents.items import ToolCallItem
from agents.mcp import MCPServerStreamableHttp, MCPServerStreamableHttpParams

from app.agent.base import AgentError, AgentReply, HistoryItem
from app.agent.market_tools import TOOLS as MARKET_TOOLS

logger = logging.getLogger(__name__)

INSTRUCTIONS = """\
You are a financial research assistant. Answer questions about stocks, forex,
crypto, and markets with current data from your tools.

Which tools to use:
- Current price of a stock or ETF: use get_quote first.
- How a stock moved over time, trends, or comparisons: use get_price_history first.
- If get_quote or get_price_history returns a result with "error", call the
  Alpha Vantage tool named in its "fallback" field instead (GLOBAL_QUOTE or
  TIME_SERIES_DAILY).
- News, top gainers and losers, company fundamentals, earnings, forex, crypto,
  and technical indicators: use the Alpha Vantage tools.

Rules:
- Always fetch data with a tool rather than relying on memory for prices or figures.
- Say which date or time the data is from, and which source it came from.
- If every source fails or reports a rate limit, say so plainly. Do not guess numbers.
- Keep answers concise and use short tables when comparing tickers.
- You provide information, not personalized investment advice. Say so if asked
  whether to buy or sell.
"""


class OpenAIAgent:
    def __init__(
        self,
        *,
        model: str,
        openai_api_key: str,
        alphavantage_api_key: str,
        mcp_url: str,
        tracing_enabled: bool = False,
    ) -> None:
        set_default_openai_key(openai_api_key, use_for_tracing=tracing_enabled)
        set_tracing_disabled(not tracing_enabled)
        # The Alpha Vantage MCP server takes the API key as a query parameter, and
        # httpx logs full request URLs at INFO level. Silence it so the key never
        # reaches the logs.
        logging.getLogger("httpx").setLevel(logging.WARNING)

        self._mcp = MCPServerStreamableHttp(
            MCPServerStreamableHttpParams(
                url=f"{mcp_url}?apikey={alphavantage_api_key}",
                timeout=15.0,
                sse_read_timeout=30.0,
            ),
            name="alphavantage",
            cache_tools_list=True,
            client_session_timeout_seconds=30.0,
            max_retry_attempts=2,
        )
        self._agent = SdkAgent(
            name="Stock Research Assistant",
            instructions=INSTRUCTIONS,
            model=model,
            tools=list(MARKET_TOOLS),  # yfinance first (issue #19)
            mcp_servers=[self._mcp],  # Alpha Vantage: fallback, news, fundamentals
        )

    async def start(self) -> None:
        await self._mcp.connect()
        logger.info("Connected to Alpha Vantage MCP server")

    async def stop(self) -> None:
        await self._mcp.cleanup()

    async def reply(self, history: list[HistoryItem], question: str) -> AgentReply:
        run_input: list[Any] = [{"role": h.role, "content": h.content} for h in history]
        run_input.append({"role": "user", "content": question})

        try:
            result = await Runner.run(self._agent, run_input, max_turns=10)
        except Exception as exc:
            # Log the exception type only: messages from HTTP errors can include
            # the request URL, which contains the API key.
            logger.error("Agent run failed: %s", type(exc).__name__)
            raise AgentError(
                "The AI assistant could not complete this request. Please try again."
            ) from exc

        return AgentReply(
            content=str(result.final_output or ""),
            tool_calls=[
                _tool_call(item) for item in result.new_items if isinstance(item, ToolCallItem)
            ],
        )


def _tool_call(item: ToolCallItem) -> dict[str, Any]:
    raw = item.raw_item
    name = getattr(raw, "name", None) or "unknown"
    arguments = getattr(raw, "arguments", None)
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            arguments = {"raw": arguments}
    return {"name": name, "arguments": arguments if isinstance(arguments, dict) else None}
