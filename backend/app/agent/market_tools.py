"""Market-data tools backed by yfinance (issue #19).

The agent prefers these for quotes and price history, so most questions don't
use Alpha Vantage's free quota (about 25 requests/day). Alpha Vantage (over MCP)
stays available as the fallback and for news, top movers, and fundamentals.

yfinance is unofficial: it reads Yahoo Finance's website data, which Yahoo
intends for personal and educational use, and it can break or be throttled
without notice. So every tool returns an *error result* naming the Alpha
Vantage tool to use instead, rather than raising. The spike in issue #18
confirmed it works from data-center networks, but not that it always will.
"""

import asyncio
import logging
import math
import re
import time
import warnings
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Literal

import yfinance as yf
from agents import function_tool

logger = logging.getLogger(__name__)

SOURCE = "Yahoo Finance (via yfinance)"
QUOTE_TTL_SECONDS = 60
HISTORY_TTL_SECONDS = 15 * 60
TOOL_TIMEOUT_SECONDS = 10.0
MAX_HISTORY_POINTS = 40

# Same rule as the watchlist and openapi.yaml (BRK.B is BRK-B on Yahoo).
_SYMBOL = re.compile(r"^[A-Za-z]{1,10}(\.[A-Za-z]{1,2})?$")

Period = Literal["5d", "1mo", "3mo", "6mo", "1y", "5y"]

# yfinance logs HTTP errors and triggers pandas deprecation warnings; keep the
# server logs readable. yfinance adds its own "show deprecation warnings" filter
# when imported, so this must run after `import yfinance` to take precedence.
logging.getLogger("yfinance").setLevel(logging.CRITICAL)
warnings.filterwarnings("ignore", module=r"^yfinance(\.|$)")


class MarketDataError(Exception):
    """Yahoo returned nothing usable for this request."""


class TTLCache:
    """Tiny in-memory cache. Per server instance; fine for a single instance."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._items: dict[tuple, tuple[float, Any]] = {}

    def get(self, key: tuple) -> Any | None:
        hit = self._items.get(key)
        if hit is None or hit[0] <= self._clock():
            self._items.pop(key, None)
            return None
        return hit[1]

    def set(self, key: tuple, value: Any, ttl: float) -> None:
        self._items[key] = (self._clock() + ttl, value)


cache = TTLCache()


def _yahoo_symbol(symbol: str) -> str:
    cleaned = symbol.strip()
    if not _SYMBOL.match(cleaned):
        raise ValueError(f"{symbol!r} is not a valid ticker symbol")
    return cleaned.upper().replace(".", "-")


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(number) else number


def _fetch_quote(yahoo_symbol: str) -> dict[str, Any]:
    info = yf.Ticker(yahoo_symbol).fast_info
    try:
        price = _number(info["last_price"])
    except KeyError:  # yfinance raises KeyError for unknown symbols
        price = None
    if price is None:
        raise MarketDataError(f"No quote found for {yahoo_symbol}")

    def field(name: str) -> Any:
        try:
            return info[name]
        except KeyError:
            return None

    previous = _number(field("previous_close"))
    change = round(price - previous, 4) if previous else None
    return {
        "symbol": yahoo_symbol.replace("-", "."),
        "price": round(price, 4),
        "previous_close": previous,
        "change": change,
        "change_percent": round(change / previous * 100, 2) if change is not None else None,
        "currency": field("currency"),
        "exchange": field("exchange"),
        "day_low": _number(field("day_low")),
        "day_high": _number(field("day_high")),
        "year_low": _number(field("year_low")),
        "year_high": _number(field("year_high")),
        "retrieved_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": SOURCE,
    }


def _fetch_history(yahoo_symbol: str, period: str) -> dict[str, Any]:
    frame = yf.Ticker(yahoo_symbol).history(period=period, auto_adjust=True)
    if frame is None or frame.empty or "Close" not in frame:
        raise MarketDataError(f"No price history found for {yahoo_symbol} ({period})")

    closes = frame["Close"].dropna()
    if closes.empty:
        raise MarketDataError(f"No price history found for {yahoo_symbol} ({period})")

    # Keep the payload small for the model: at most MAX_HISTORY_POINTS evenly
    # spaced closes, always including the first and last.
    step = max(1, math.ceil(len(closes) / MAX_HISTORY_POINTS))
    positions = list(range(0, len(closes), step))
    if positions[-1] != len(closes) - 1:
        positions.append(len(closes) - 1)
    sampled = closes.iloc[positions]

    first, last = float(closes.iloc[0]), float(closes.iloc[-1])
    return {
        "symbol": yahoo_symbol.replace("-", "."),
        "period": period,
        "start_date": closes.index[0].date().isoformat(),
        "end_date": closes.index[-1].date().isoformat(),
        "start_close": round(first, 4),
        "end_close": round(last, 4),
        "change_percent": round((last - first) / first * 100, 2) if first else None,
        "high_close": round(float(closes.max()), 4),
        "low_close": round(float(closes.min()), 4),
        "trading_days": len(closes),
        "closes": [
            {"date": index.date().isoformat(), "close": round(float(value), 4)}
            for index, value in sampled.items()
        ],
        "source": SOURCE,
    }


async def _cached(key: tuple, ttl: float, fetch: Callable[..., dict], *args: Any) -> dict:
    hit = cache.get(key)
    if hit is not None:
        return hit
    # yfinance is blocking; keep the event loop (and other requests) free.
    result = await asyncio.to_thread(fetch, *args)
    cache.set(key, result, ttl)
    return result


def _failure(exc: Exception, fallback_tool: str) -> dict[str, str]:
    # Only the exception type goes to the logs; the message reaches the model.
    logger.warning("yfinance tool failed: %s", type(exc).__name__)
    return {
        "error": str(exc) or type(exc).__name__,
        "fallback": f"Use the Alpha Vantage {fallback_tool} tool instead.",
    }


async def get_quote(symbol: str) -> dict[str, Any]:
    """Get the latest price and today's change for a stock or ETF.

    Use this first for current-price questions. If the result contains
    "error", use the Alpha Vantage GLOBAL_QUOTE tool instead.

    Args:
        symbol: Ticker symbol, e.g. AAPL, MSFT, or BRK.B.
    """
    try:
        yahoo_symbol = _yahoo_symbol(symbol)
        return await _cached(("quote", yahoo_symbol), QUOTE_TTL_SECONDS, _fetch_quote, yahoo_symbol)
    except Exception as exc:
        return _failure(exc, "GLOBAL_QUOTE")


async def get_price_history(symbol: str, period: Period = "1mo") -> dict[str, Any]:
    """Get daily closing prices over a period, with the period's change, high, and low.

    Use this first for questions about how a stock moved, trends, or
    comparisons over time. If the result contains "error", use the Alpha
    Vantage TIME_SERIES_DAILY tool instead.

    Args:
        symbol: Ticker symbol, e.g. AAPL, MSFT, or BRK.B.
        period: How far back to look: 5d, 1mo, 3mo, 6mo, 1y, or 5y.
    """
    try:
        yahoo_symbol = _yahoo_symbol(symbol)
        return await _cached(
            ("history", yahoo_symbol, period),
            HISTORY_TTL_SECONDS,
            _fetch_history,
            yahoo_symbol,
            period,
        )
    except Exception as exc:
        return _failure(exc, "TIME_SERIES_DAILY")


TOOLS = [
    function_tool(get_quote, timeout=TOOL_TIMEOUT_SECONDS),
    function_tool(get_price_history, timeout=TOOL_TIMEOUT_SECONDS),
]
