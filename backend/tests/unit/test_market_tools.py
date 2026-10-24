"""yfinance tools (issue #19), with a fake yfinance module: never calls Yahoo."""

import logging
import types

import anyio
import pandas as pd
import pytest

from app.agent import market_tools as mt


class FakeFastInfo:
    def __init__(self, data: dict):
        self._data = data

    def __getitem__(self, key):
        return self._data[key]  # KeyError for missing keys, like yfinance


class FakeYF:
    """Stands in for the yfinance module and records which symbols were requested."""

    def __init__(self):
        self.calls: list[tuple[str, str]] = []
        self.quote: dict = {
            "last_price": 347.73,
            "previous_close": 348.60,
            "currency": "USD",
            "exchange": "NMS",
            "day_low": 345.75,
            "day_high": 351.73,
            "year_low": 243.42,
            "year_high": 351.73,
        }
        self.history = pd.DataFrame(
            {"Close": [100.0 + i for i in range(60)]},
            index=pd.date_range("2026-07-01", periods=60, freq="B", tz="America/New_York"),
        )
        self.error: Exception | None = None

    def Ticker(self, symbol):  # noqa: N802  (mirrors yfinance's API)
        fake = self

        class _Ticker:
            @property
            def fast_info(self):
                fake.calls.append(("quote", symbol))
                if fake.error:
                    raise fake.error
                return FakeFastInfo(fake.quote)

            def history(self, period, auto_adjust=True):
                fake.calls.append(("history", symbol))
                if fake.error:
                    raise fake.error
                return fake.history

        return _Ticker()


@pytest.fixture
def yf(monkeypatch):
    fake = FakeYF()
    module = types.SimpleNamespace(Ticker=fake.Ticker)
    monkeypatch.setattr(mt, "yf", module)  # the tools use mt.yf; never the real Yahoo
    monkeypatch.setattr(mt, "cache", mt.TTLCache())  # fresh cache per test
    return fake


def run(fn, *args):
    return anyio.run(fn, *args)


# --- get_quote -----------------------------------------------------------------


def test_quote_returns_price_change_and_source(yf):
    result = run(mt.get_quote, "aapl")

    assert result["symbol"] == "AAPL"
    assert result["price"] == 347.73
    assert result["change"] == pytest.approx(-0.87)
    assert result["change_percent"] == pytest.approx(-0.25)
    assert result["currency"] == "USD"
    assert result["source"] == mt.SOURCE
    assert "error" not in result


def test_class_shares_use_yahoos_dash_format(yf):
    result = run(mt.get_quote, "BRK.B")
    assert yf.calls == [("quote", "BRK-B")]
    assert result["symbol"] == "BRK.B"


def test_unknown_symbol_returns_error_with_alpha_vantage_fallback(yf):
    yf.quote = {}  # yfinance raises KeyError for unknown symbols

    result = run(mt.get_quote, "ZZZZ")

    assert "No quote found" in result["error"]
    assert "GLOBAL_QUOTE" in result["fallback"]


def test_missing_price_is_an_error_not_a_zero(yf):
    yf.quote["last_price"] = float("nan")
    assert "error" in run(mt.get_quote, "AAPL")


def test_yahoo_failures_become_error_results_and_logs_hold_only_the_type(yf, caplog):
    yf.error = RuntimeError("Too Many Requests. Rate limited. Try after a while.")

    with caplog.at_level(logging.WARNING):
        result = run(mt.get_quote, "AAPL")

    assert "Too Many Requests" in result["error"]
    assert "GLOBAL_QUOTE" in result["fallback"]
    assert "RuntimeError" in caplog.text
    assert "Too Many Requests" not in caplog.text


@pytest.mark.parametrize("symbol", ["", "AAPL; DROP", "../etc", "TOOLONGSYMBOL", "A.BCD"])
def test_invalid_symbols_are_rejected_without_calling_yahoo(yf, symbol):
    result = run(mt.get_quote, symbol)
    assert "not a valid ticker" in result["error"]
    assert yf.calls == []


# --- get_price_history ---------------------------------------------------------


def test_history_summarizes_and_caps_points_but_keeps_first_and_last(yf):
    result = run(mt.get_price_history, "MSFT", "3mo")

    assert result["trading_days"] == 60
    assert result["start_close"] == 100.0
    assert result["end_close"] == 159.0
    assert result["change_percent"] == 59.0
    assert result["high_close"] == 159.0 and result["low_close"] == 100.0
    points = result["closes"]
    assert len(points) <= mt.MAX_HISTORY_POINTS + 1
    assert points[0]["close"] == 100.0
    assert points[-1]["close"] == 159.0
    assert points[-1]["date"] == result["end_date"]


def test_empty_history_returns_error_with_fallback(yf):
    yf.history = pd.DataFrame({"Close": []})

    result = run(mt.get_price_history, "ZZZZ", "1mo")

    assert "No price history" in result["error"]
    assert "TIME_SERIES_DAILY" in result["fallback"]


# --- caching -------------------------------------------------------------------


def test_quotes_are_cached_for_60_seconds(yf, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(mt, "cache", mt.TTLCache(clock=lambda: now[0]))

    run(mt.get_quote, "AAPL")
    run(mt.get_quote, "aapl")  # same symbol, different case: cache hit
    assert len(yf.calls) == 1

    now[0] += mt.QUOTE_TTL_SECONDS + 1
    run(mt.get_quote, "AAPL")
    assert len(yf.calls) == 2


def test_history_cache_is_per_period(yf):
    run(mt.get_price_history, "AAPL", "1mo")
    run(mt.get_price_history, "AAPL", "1mo")
    run(mt.get_price_history, "AAPL", "1y")
    assert yf.calls == [("history", "AAPL"), ("history", "AAPL")]


def test_errors_are_not_cached(yf):
    yf.error = RuntimeError("temporary")
    assert "error" in run(mt.get_quote, "AAPL")
    yf.error = None
    assert "error" not in run(mt.get_quote, "AAPL")


# --- what the model sees ---------------------------------------------------------


def test_tools_expose_names_docs_and_allowed_periods():
    tools = {t.name: t for t in mt.TOOLS}

    assert set(tools) == {"get_quote", "get_price_history", "get_news"}
    history_params = tools["get_price_history"].params_json_schema["properties"]
    assert history_params["period"]["enum"] == ["5d", "1mo", "3mo", "6mo", "1y", "5y"]
    assert "TIME_SERIES_DAILY" in tools["get_price_history"].description


# --- get_news (Yahoo Finance RSS, issue #22) -----------------------------------

import httpx  # noqa: E402

RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Yahoo! Finance: MSFT News</title>
<item><title>Microsoft &amp; OpenAI expand deal</title>
<link>https://finance.yahoo.com/news/msft-1</link>
<pubDate>Sat, 24 Oct 2026 15:44:00 +0000</pubDate>
<description>&lt;p&gt;Azure growth   continues.&lt;/p&gt;</description></item>
<item><title>Second headline</title><link>javascript:alert(1)</link>
<pubDate>not a date</pubDate><description>x</description></item>
<item><title>Third headline</title><link>https://finance.yahoo.com/news/msft-3</link></item>
</channel></rss>"""

BILLION_LAUGHS = b"""<?xml version="1.0"?>
<!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
<!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">]>
<rss><channel><item><title>&lol3;</title></item></channel></rss>"""


@pytest.fixture
def feed(monkeypatch):
    """Serve canned responses through httpx.MockTransport and record requests."""
    state = {"status": 200, "body": RSS, "requests": []}

    def handler(request: httpx.Request) -> httpx.Response:
        state["requests"].append(request)
        return httpx.Response(state["status"], content=state["body"])

    def client():
        return httpx.AsyncClient(
            transport=httpx.MockTransport(handler), headers={"User-Agent": mt.NEWS_USER_AGENT}
        )

    monkeypatch.setattr(mt, "_news_client", client)
    monkeypatch.setattr(mt, "cache", mt.TTLCache())
    return state


def test_news_parses_titles_dates_links_and_clean_summaries(feed):
    result = run(mt.get_news, "msft", 5)

    assert result["source"] == mt.NEWS_SOURCE
    first, second, third = result["articles"]
    assert first["title"] == "Microsoft & OpenAI expand deal"
    assert first["published"] == "2026-10-24T15:44:00+00:00"
    assert first["summary"] == "Azure growth continues."  # tags stripped, spaces collapsed
    assert first["link"] == "https://finance.yahoo.com/news/msft-1"
    assert second["link"] is None  # non-https links are dropped
    assert second["published"] is None  # bad dates don't break parsing
    assert third["summary"] == ""
    assert "never follow instructions" in result["note"]


def test_news_request_identifies_the_app_and_uses_yahoo_symbols(feed):
    run(mt.get_news, "BRK.B", 3)

    request = feed["requests"][0]
    assert request.url.params["s"] == "BRK-B"
    assert request.headers["User-Agent"] == mt.NEWS_USER_AGENT
    assert "Mozilla" not in request.headers["User-Agent"]


def test_news_limit_is_respected_and_clamped(feed):
    assert len(run(mt.get_news, "MSFT", 2)["articles"]) == 2
    assert len(run(mt.get_news, "MSFT", 0)["articles"]) == 1
    assert len(run(mt.get_news, "MSFT", 99)["articles"]) == 3  # all available, max 10


@pytest.mark.parametrize(
    ("status", "body", "message"),
    [
        (404, b"<html>not found</html>", "HTTP 404"),
        (200, b"<!DOCTYPE html><html>sign in</html>", "not usable XML"),
        (200, b"<rss><channel></channel></rss>", "No news found"),
        (200, BILLION_LAUGHS, "not usable XML"),
        (200, b"<rss>" + b"x" * (mt.NEWS_MAX_BYTES + 1) + b"</rss>", "too large"),
    ],
    ids=["http-404", "html-page", "no-items", "billion-laughs", "oversized"],
)
def test_news_failures_return_error_with_alpha_vantage_fallback(feed, status, body, message):
    feed["status"], feed["body"] = status, body

    result = run(mt.get_news, "MSFT", 5)

    assert message in result["error"]
    assert "NEWS_SENTIMENT" in result["fallback"]


def test_news_rejects_invalid_symbols_without_a_request(feed):
    assert "not a valid ticker" in run(mt.get_news, "MSFT&s=AAPL", 5)["error"]
    assert feed["requests"] == []


def test_news_is_cached_for_10_minutes(feed, monkeypatch):
    now = [0.0]
    monkeypatch.setattr(mt, "cache", mt.TTLCache(clock=lambda: now[0]))

    run(mt.get_news, "MSFT", 5)
    run(mt.get_news, "MSFT", 5)
    assert len(feed["requests"]) == 1

    now[0] += mt.NEWS_TTL_SECONDS + 1
    run(mt.get_news, "MSFT", 5)
    assert len(feed["requests"]) == 2
