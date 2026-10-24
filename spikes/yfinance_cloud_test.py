"""Spike (issue #18): does yfinance work from this machine's network?

    uvx --with yfinance python spikes/yfinance_cloud_test.py

Runs the same requests locally and on a GitHub Actions runner (data-center IP,
a stand-in for Render). Empty results count as failures, because yfinance
often returns empty data instead of raising when Yahoo blocks a request.
Always exits 0; the summary line is the result.
"""

import json
import platform
import time

import yfinance as yf

TICKERS = ["AAPL", "MSFT", "NVDA", "AMD", "GOOGL", "TSLA", "AMZN", "META", "JPM", "XOM"]
results = []


def attempt(name, fn):
    start = time.time()
    try:
        value = fn()
        ok = value not in (None, 0, 0.0)  # empty data counts as a failure
        error = None if ok else "empty result"
    except Exception as exc:  # noqa: BLE001  (we want to record every failure kind)
        value, ok, error = None, False, f"{type(exc).__name__}: {str(exc)[:140]}"
    results.append(
        {"test": name, "ok": ok, "seconds": round(time.time() - start, 2), "value": value, "error": error}
    )


for t in TICKERS:
    attempt(f"quote {t}", lambda t=t: round(float(yf.Ticker(t).fast_info["last_price"]), 2))
attempt("history AAPL 1mo (rows)", lambda: len(yf.Ticker("AAPL").history(period="1mo")))
attempt(
    "download 5 tickers 5d (rows)",
    lambda: yf.download(TICKERS[:5], period="5d", progress=False, auto_adjust=True).dropna().shape[0],
)
attempt("news NVDA (items)", lambda: len(yf.Ticker("NVDA").news or []))
for i in range(20):
    attempt(f"burst {i + 1:02d} history 5d", lambda i=i: len(yf.Ticker(TICKERS[i % 10]).history(period="5d")))

failed = [r for r in results if not r["ok"]]
errors = sorted({r["error"] for r in failed})
print(json.dumps(results, indent=1))
print(
    f"SUMMARY yfinance={yf.__version__} python={platform.python_version()} "
    f"ok={len(results) - len(failed)}/{len(results)} "
    f"burst_ok={sum(r['ok'] for r in results if r['test'].startswith('burst'))}/20 "
    f"avg_s={sum(r['seconds'] for r in results) / len(results):.2f} "
    f"errors={errors}"
)
