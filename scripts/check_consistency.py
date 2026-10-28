import json
from datetime import datetime
import math
from pathlib import Path

data = Path(__file__).resolve().parents[1] / "data"
market = json.loads((data / "market.json").read_text(encoding="utf-8"))
morning = json.loads((data / "morning.json").read_text(encoding="utf-8"))
market_time = market.get("generated_at_kst") or market.get("generated_at_utc")
source_time = morning.get("market_snapshot_at")
if not market_time or not source_time:
    raise SystemExit("FAIL: missing market snapshot timestamp")
try:
    market_dt = datetime.fromisoformat(market_time.replace("Z", "+00:00"))
    source_dt = datetime.fromisoformat(source_time.replace("Z", "+00:00"))
except (ValueError, TypeError, AttributeError):
    raise SystemExit("FAIL: invalid market snapshot timestamp")
if market_dt.tzinfo is None or source_dt.tzinfo is None:
    raise SystemExit("FAIL: market snapshot timestamp missing timezone")
delta = abs((market_dt - source_dt).total_seconds())
if not math.isfinite(delta):
    raise SystemExit("FAIL: invalid market snapshot delta")
if delta > 2:
    raise SystemExit(f"FAIL: briefing uses different market snapshot ({delta:.1f}s)")
labels = {"sp500": "미국 대형주", "sox": "반도체", "usdkrw": "원/달러"}
indicators = {row.get("name"): row for row in morning.get("indicators", [])}
for key, label in labels.items():
    quote = market.get("markets", {}).get(key, {})
    if quote.get("status") != "ok":
        raise SystemExit(f"FAIL: required {key} quote unavailable")
    value = quote.get("change_percent")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise SystemExit(f"FAIL: invalid {key} percentage")
    row = indicators.get(label)
    if not row or row.get("change_percent") != quote.get("change_percent") or row.get("market_date") != quote.get("market_date"):
        raise SystemExit(f"FAIL: {key} mismatch")
if morning.get("market_snapshot_fresh") is not True:
    raise SystemExit("FAIL: morning briefing marks market snapshot as stale")
intelligence = json.loads((data / "intelligence.json").read_text(encoding="utf-8"))
intel_time = intelligence.get("market_snapshot_at")
if not intel_time:
    raise SystemExit("FAIL: intelligence missing market snapshot timestamp")
try:
    intel_dt = datetime.fromisoformat(intel_time.replace("Z", "+00:00"))
except (ValueError, TypeError, AttributeError):
    raise SystemExit("FAIL: invalid intelligence market snapshot timestamp")
if intel_dt.tzinfo is None:
    raise SystemExit("FAIL: intelligence market snapshot timestamp missing timezone")
intel_delta = abs((market_dt - intel_dt).total_seconds())
if intel_delta > 2:
    raise SystemExit(f"FAIL: intelligence uses different market snapshot ({intel_delta:.1f}s)")
signals = intelligence.get("market_signals", {})
for key in ("sp500", "sox", "usdkrw"):
    quote = market["markets"][key]
    signal = signals.get(key, {})
    if signal.get("status") != "ok" or signal.get("change_percent") != quote["change_percent"] or signal.get("market_date") != quote.get("market_date"):
        raise SystemExit(f"FAIL: intelligence {key} mismatch")
print("PASS: morning briefing and intelligence match market snapshot")
