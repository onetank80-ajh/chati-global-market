"""Fetch indicative daily market closes for the Chati market briefing app."""
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import yfinance as yf

SYMBOLS = {
    "nasdaq": ("^IXIC", "NASDAQ Composite", "points"),
    "sp500": ("^GSPC", "S&P 500", "points"),
    "dow": ("^DJI", "Dow Jones", "points"),
    "sox": ("^SOX", "PHLX Semiconductor", "points"),
    "usdkrw": ("KRW=X", "USD/KRW", "KRW per USD"),
}


def fetch(symbol, name, unit):
    try:
        frame = yf.Ticker(symbol).history(period="10d", interval="1d", auto_adjust=False)
        closes = frame["Close"].dropna()
        if len(closes) < 2:
            raise ValueError("Fewer than two daily closes")
        previous, latest = float(closes.iloc[-2]), float(closes.iloc[-1])
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
    now = datetime.now(timezone.utc)
    items = {key: fetch(*spec) for key, spec in SYMBOLS.items()}
    output = {
        "schema_version": 1,
        "generated_at_utc": now.isoformat(),
        "generated_at_kst": now.astimezone(ZoneInfo("Asia/Seoul")).isoformat(),
        "data_kind": "daily_close_snapshot_not_live",
        "source": "Yahoo Finance via yfinance (unofficial, may be delayed)",
        "markets": items,
    }
    path = Path("data/market.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Saved", path, "successful symbols:", sum(v["status"] == "ok" for v in items.values()))
    if all(v["status"] != "ok" for v in items.values()):
        raise RuntimeError("No market data available; refusing to publish an all-error snapshot")


if __name__ == "__main__":
    main()
