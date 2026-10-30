"""Send a Korean morning market notification via ntfy.
Run after market + verification jobs. No private account data is sent.
Set NTFY_TOPIC (unguessable) and optionally NTFY_BASE_URL/NTFY_TOKEN.
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import quote
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
ROOT = Path(__file__).resolve().parent.parent

def load(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))

def main():
    now = datetime.now(timezone.utc).astimezone(KST)
    if now.weekday() >= 5:
        raise RuntimeError("Weekend; no notification sent")
    # Do not send a late morning briefing as if it were on time.
    # GitHub scheduled workflows can be delayed; backup is allowed through 08:00 KST.
    if (now.hour, now.minute) < (7, 30):
        raise RuntimeError("Morning push starts at 07:30 KST; refusing early notification")
    if (now.hour, now.minute) >= (8, 0):
        raise RuntimeError("Morning push cutoff 08:00 KST passed; refusing late notification")
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        raise RuntimeError("NTFY_TOPIC is not set. No notification sent.")
    if not all(c.isascii() and (c.isalnum() or c in "-_") for c in topic) or len(topic) < 24:
        raise ValueError("Use a random ASCII topic of at least 24 characters")
    market = load("market.json")
    snapshot = datetime.fromisoformat(market["generated_at_utc"].replace("Z","+00:00"))
    age = (now.astimezone(timezone.utc)-snapshot).total_seconds()/3600
    if not 0 <= age <= 12:
        raise RuntimeError(f"Market snapshot stale: {age:.1f} hours")
    mk = market.get("markets", {})
    # A fresh JSON timestamp does not guarantee fresh US closing prices.
    # Allow one additional calendar day for US exchange holidays.
    from datetime import timedelta
    # On Tuesday KST, a US Monday holiday leaves Friday as the latest close.
    # Permit Friday only on Tuesdays; all other days retain the tighter guard.
    expected = now.date() - timedelta(days=3 if now.weekday() == 0 else 1)
    oldest = expected - timedelta(days=1)
    if now.weekday() == 1:
        oldest = now.date() - timedelta(days=4)
    for key in ("sp500", "sox"):
        item = mk.get(key, {})
        try:
            quoted = datetime.strptime(item["market_date"], "%Y-%m-%d").date()
        except (KeyError, TypeError, ValueError):
            raise RuntimeError(f"Missing US market date: {key}")
        if quoted < oldest or quoted > now.date():
            raise RuntimeError(f"Outdated US market close: {key} {quoted}; expected around {expected}")
    lines = []
    for key, label in (("sp500","S&P500"),("nasdaq","나스닥"),("sox","반도체 SOX"),("usdkrw","달러/원")):
        item = mk.get(key, {})
        if item.get("status") == "ok" and isinstance(item.get("change_percent"), (float,int)):
            lines.append(f"{label}: {item['change_percent']:+.2f}% ({item.get('market_date','날짜 미상')})")
    if len(lines) < 3:
        raise RuntimeError("Not enough market indicators; no notification")
    prediction = "방향 예측: 기록 미확인"
    try:
        rec = load("verification.json").get("records", [])
        today = now.date().isoformat()
        matches = [r for r in rec if r.get("date")==today and r.get("market")=="kospi"]
        if matches:
            direction = {"up":"상승 우세","down":"하락 우세","flat":"중립"}.get(matches[-1].get("prediction"),"미확인")
            prediction = f"코스피 규칙 기반 예측: {direction}"
    except (OSError, ValueError, TypeError):
        pass
    body = "\n".join([f"{now:%Y-%m-%d} 오전 시장 브리핑", *lines, prediction,
                        "참고용 종가 데이터이며 실시간 시세·투자 권유가 아닙니다."])
    base = os.environ.get("NTFY_BASE_URL", "https://ntfy.sh").rstrip("/")
    if not base.startswith("https://"):
        raise ValueError("HTTPS required")
    url = base + "/" + quote(topic, safe="")
    req = Request(url, data=body.encode("utf-8"), method="POST",
                  headers={"Title":"Chati Morning Briefing", "Tags":"chart_with_upwards_trend",
                           "Click":"https://onetank80-ajh.github.io/chati-global-market/",
                           "Content-Type":"text/plain; charset=utf-8"})
    token = os.environ.get("NTFY_TOKEN", "").strip()
    if token:
        req.add_header("Authorization", "Bearer " + token)
    print('PUSH_HTTP_STARTED_KST=' + datetime.now(timezone.utc).astimezone(KST).isoformat(), flush=True)
    with urlopen(req, timeout=20) as response:
        if not 200 <= response.status < 300:
            raise RuntimeError(f"Notification failed: HTTP {response.status}")
    print('PUSH_HTTP_SUCCEEDED_KST=' + datetime.now(timezone.utc).astimezone(KST).isoformat(), flush=True)
    print("Push notification sent; snapshot age hours:", round(age, 2))

if __name__ == "__main__":
    main()
