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
        print("Weekend; no notification")
        return
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
    with urlopen(req, timeout=20) as response:
        if not 200 <= response.status < 300:
            raise RuntimeError(f"Notification failed: HTTP {response.status}")
    print("Push notification sent; snapshot age hours:", round(age, 2))

if __name__ == "__main__":
    main()
