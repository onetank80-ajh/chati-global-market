"""Fetch indicative daily market closes for the Chati market briefing app."""
import json
import math
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yfinance as yf

# Required briefing indicators first: fail fast if a critical provider is down.
# Optional benchmarks follow and never determine whether a snapshot is publishable.
SYMBOLS = {
    "sp500": ("^GSPC", "S&P 500", "points"),
    "sox": ("^SOX", "PHLX Semiconductor", "points"),
    "usdkrw": ("KRW=X", "USD/KRW", "KRW per USD"),
    "nasdaq": ("^IXIC", "NASDAQ Composite", "points"),
    "dow": ("^DJI", "Dow Jones", "points"),
}


def fetch(symbol, name, unit):
    try:
        frame = yf.Ticker(symbol).history(period="10d", interval="1d", auto_adjust=False, timeout=15)
        closes = frame["Close"].dropna()
        if len(closes) < 2:
            raise ValueError("Fewer than two daily closes")
        previous, latest = float(closes.iloc[-2]), float(closes.iloc[-1])
        if not all(math.isfinite(v) and v > 0 for v in (previous, latest)):
            raise ValueError("Non-finite or non-positive daily close")
        return {
            "symbol": symbol,
            "name": name,
            "unit": unit,
            "close": round(latest, 4),
            "previous_close": round(previous, 4),
            "change": round(latest - previous, 4),
            "change_percent": round((latest / previous - 1) * 100, 3),
            "market_date": closes.index[-1].strftime("%Y-%m-%d"),
            "status": "ok",
        }
    except Exception as exc:
        return {"symbol": symbol, "name": name, "unit": unit,
                "status": "unavailable", "error": str(exc)[:180]}


def main():
    items = {}
    for key, spec in SYMBOLS.items():
        print(f"Fetching quote: {key} ({spec[0]})", flush=True)
        items[key] = fetch(*spec)
        print(f"Quote result: {key} status={items[key].get('status', 'missing')}", flush=True)
        # Do not spend additional provider requests on optional indices when a
        # required indicator has already failed; the whole attempt must retry.
        if key in ("sp500", "sox", "usdkrw") and items[key].get("status") != "ok":
            raise RuntimeError(
                f"Required market data unavailable: {key} "
                f"({items[key].get('symbol', key)}): {items[key].get('error', 'unknown error')}"
            )
    now = datetime.now(timezone.utc)
    output = {
        "schema_version": 1,
        "generated_at_utc": now.isoformat(),
        "generated_at_kst": now.astimezone(timezone(timedelta(hours=9))).isoformat(),
        "data_kind": "daily_close_snapshot_not_live",
        "source": "Yahoo Finance via yfinance (unofficial, may be delayed)",
        "markets": items,
    }
    required = ("sp500", "sox", "usdkrw")
    missing = [key for key in required if items[key]["status"] != "ok"]
    for key, item in items.items():
        if item["status"] != "ok":
            print(f"Quote unavailable: {key} ({item.get('symbol', key)}): {item.get('error', 'unknown error')}", flush=True)
    if missing:
        details = "; ".join(f"{key} ({items[key].get('symbol', key)}): {items[key].get('error', 'unknown error')}" for key in missing)
        raise RuntimeError("Required market data unavailable; keeping previous market.json. " + details)
    path = Path("data/market.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write beside the destination and atomically replace only after success.
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".market-", suffix=".json", delete=False) as handle:
            temp_name = handle.name
            handle.write(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
        os.replace(temp_name, path)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)
    print("Saved", path, "successful symbols:", sum(v["status"] == "ok" for v in items.values()))


if __name__ == "__main__":
    main()
