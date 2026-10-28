import json
from datetime import datetime
from pathlib import Path

data = Path(__file__).resolve().parents[1] / "data"
market = json.loads((data / "market.json").read_text(encoding="utf-8"))
morning = json.loads((data / "morning.json").read_text(encoding="utf-8"))
market_time = market.get("generated_at_kst") or market.get("generated_at_utc")
source_time = morning.get("market_snapshot_at")
if not market_time or not source_time:
    raise SystemExit("FAIL: missing market snapshot timestamp")
delta = abs((datetime.fromisoformat(market_time) - datetime.fromisoformat(source_time)).total_seconds())
if delta > 2:
    raise SystemExit(f"FAIL: briefing uses different market snapshot ({delta:.1f}s)")
labels = {"sp500": "미국 대형주", "sox": "반도체", "usdkrw": "원/달러"}
indicators = {row.get("name"): row for row in morning.get("indicators", [])}
for key, label in labels.items():
    quote = market.get("markets", {}).get(key, {})
    if quote.get("status") != "ok":
        raise SystemExit(f"FAIL: required {key} quote unavailable")
    row = indicators.get(label)
    if not row or row.get("change_percent") != quote.get("change_percent") or row.get("market_date") != quote.get("market_date"):
        raise SystemExit(f"FAIL: {key} mismatch")
if morning.get("market_snapshot_fresh") is not True:
    raise SystemExit("FAIL: morning briefing marks market snapshot as stale")
print("PASS: morning briefing matches market snapshot")
