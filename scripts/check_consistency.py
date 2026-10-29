import json
from datetime import datetime, timezone
import math
from pathlib import Path

data = Path(__file__).resolve().parents[1] / "data"
market = json.loads((data / "market.json").read_text(encoding="utf-8"))
morning = json.loads((data / "morning.json").read_text(encoding="utf-8"))
if not isinstance(market, dict) or not isinstance(morning, dict):
    raise SystemExit("FAIL: malformed market or morning document")
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
market_age_hours = (datetime.now(timezone.utc) - market_dt).total_seconds() / 3600
if not math.isfinite(market_age_hours) or not 0 <= market_age_hours <= 12:
    raise SystemExit("FAIL: market snapshot is stale or future-dated")
delta = abs((market_dt - source_dt).total_seconds())
if not math.isfinite(delta):
    raise SystemExit("FAIL: invalid market snapshot delta")
if delta > 2:
    raise SystemExit(f"FAIL: briefing uses different market snapshot ({delta:.1f}s)")
def validate_generation_time(document, label):
    stamp = document.get("generated_at_kst") or document.get("generated_at_utc")
    try:
        generated = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except (ValueError, TypeError, AttributeError):
        raise SystemExit(f"FAIL: invalid {label} generation timestamp")
    if generated.tzinfo is None:
        raise SystemExit(f"FAIL: {label} generation timestamp missing timezone")
    # Recovery can run at 09:30 after an 08:17 market snapshot; allow 3h while keeping the separate 12h market freshness guard.
    generation_age = (generated - market_dt).total_seconds()
    if not math.isfinite(generation_age) or generation_age < 0 or generation_age > 3 * 3600 or (generated - datetime.now(timezone.utc)).total_seconds() > 120:
        raise SystemExit(f"FAIL: {label} generation time outside market snapshot window")

validate_generation_time(morning, "morning")
labels = {"sp500": "미국 대형주", "sox": "반도체", "usdkrw": "원/달러"}
indicator_rows = morning.get("indicators", [])
if not isinstance(indicator_rows, list) or any(not isinstance(row, dict) for row in indicator_rows):
    raise SystemExit("FAIL: malformed morning indicators")
indicator_names = [row.get("name") for row in indicator_rows]
if any(not isinstance(name, str) for name in indicator_names):
    raise SystemExit("FAIL: malformed morning indicator name")
if len(indicator_names) != len(set(indicator_names)):
    raise SystemExit("FAIL: duplicate morning indicator names")
indicators = {row.get("name"): row for row in indicator_rows}
if len(indicators) != len(indicator_rows):
    raise SystemExit("FAIL: duplicate morning indicators")
quotes = market.get("markets", {})
if not isinstance(quotes, dict):
    raise SystemExit("FAIL: malformed market quotes")
for key, label in labels.items():
    quote = quotes.get(key, {})
    if not isinstance(quote, dict):
        raise SystemExit(f"FAIL: malformed {key} quote")
    if quote.get("status") != "ok":
        raise SystemExit(f"FAIL: required {key} quote unavailable")
    date_text = quote.get("market_date")
    if not isinstance(date_text, str) or len(date_text) != 10:
        raise SystemExit(f"FAIL: invalid {key} market date")
    try:
        trading_day = datetime.strptime(date_text, "%Y-%m-%d").date()
    except ValueError:
        raise SystemExit(f"FAIL: invalid {key} market date")
    calendar_age = (datetime.now(timezone.utc).date() - trading_day).days
    if calendar_age < -1 or calendar_age > 7:
        raise SystemExit(f"FAIL: stale or future {key} market date")
    market_date = quote.get("market_date")
    if not isinstance(market_date, str):
        raise SystemExit(f"FAIL: missing {key} market date")
    try:
        if datetime.strptime(market_date, "%Y-%m-%d").date().isoformat() != market_date:
            raise ValueError("noncanonical market date")
    except ValueError:
        raise SystemExit(f"FAIL: invalid {key} market date")
    value = quote.get("change_percent")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise SystemExit(f"FAIL: invalid {key} percentage")
    row = indicators.get(label)
    if row and (isinstance(row.get("change_percent"), bool) or not isinstance(row.get("change_percent"), (int, float)) or not math.isfinite(row["change_percent"])):
        raise SystemExit(f"FAIL: invalid morning {key} percentage")
    if not row or row.get("change_percent") != quote.get("change_percent") or row.get("market_date") != quote.get("market_date"):
        raise SystemExit(f"FAIL: {key} mismatch")
if quotes["sp500"]["market_date"] != quotes["sox"]["market_date"]:
    raise SystemExit("FAIL: US market indices have different trading dates")
if morning.get("market_snapshot_fresh") is not True:
    raise SystemExit("FAIL: morning briefing marks market snapshot as stale")
intelligence = json.loads((data / "intelligence.json").read_text(encoding="utf-8"))
if not isinstance(intelligence, dict):
    raise SystemExit("FAIL: malformed intelligence document")
validate_generation_time(intelligence, "intelligence")
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
if not math.isfinite(intel_delta):
    raise SystemExit("FAIL: invalid intelligence snapshot delta")
if intel_delta > 2:
    raise SystemExit(f"FAIL: intelligence uses different market snapshot ({intel_delta:.1f}s)")
signals = intelligence.get("market_signals", {})
if not isinstance(signals, dict):
    raise SystemExit("FAIL: malformed intelligence signals")
for key in ("sp500", "sox", "usdkrw"):
    quote = quotes[key]
    signal = signals.get(key, {})
    if not isinstance(signal, dict):
        raise SystemExit(f"FAIL: malformed intelligence {key} signal")
    signal_value = signal.get("change_percent")
    if isinstance(signal_value, bool) or not isinstance(signal_value, (int, float)) or not math.isfinite(signal_value):
        raise SystemExit(f"FAIL: invalid intelligence {key} percentage")
    if signal.get("status") != "ok" or signal_value != quote["change_percent"] or signal.get("market_date") != quote.get("market_date"):
        raise SystemExit(f"FAIL: intelligence {key} mismatch")
print("PASS: morning briefing and intelligence match market snapshot")
