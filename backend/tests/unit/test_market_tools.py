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

    assert set(tools) == {"get_quote", "get_price_history"}
    history_params = tools["get_price_history"].params_json_schema["properties"]
    assert history_params["period"]["enum"] == ["5d", "1mo", "3mo", "6mo", "1y", "5y"]
    assert "TIME_SERIES_DAILY" in tools["get_price_history"].description
