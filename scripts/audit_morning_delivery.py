"""Read-only audit of the latest morning push and briefing timestamps."""
import json
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def audit(push, morning):
    sent = datetime.fromisoformat(push["last_sent_at_kst"]).astimezone(KST)
    generated = datetime.fromisoformat(morning["generated_at_kst"]).astimezone(KST)
    deadline = datetime.combine(sent.date(), time(7, 30), KST)
    same_day = generated.date() == sent.date()
    return {
        "date_kst": sent.date().isoformat(),
        "push_http_success_recorded": True,
        "push_delay_seconds": round((sent - deadline).total_seconds()),
        "push_on_time": sent <= deadline,
        "briefing_generated_same_day": same_day,
        "briefing_delay_seconds": round((generated - deadline).total_seconds()) if same_day else None,
        "briefing_on_time": generated <= deadline if same_day else None,
        "device_receipt_verified": False,
        "limitations": [
            "Push timestamp is the status-recording time, not the exact HTTP response time.",
            "The briefing file can be regenerated after the push; this does not establish what content was sent.",
            "One latest-day record cannot establish a multi-day on-time rate.",
        ],
    }


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1] / "data"
    push = json.loads((root / "push_status.json").read_text(encoding="utf-8"))
    morning = json.loads((root / "morning.json").read_text(encoding="utf-8"))
    print(json.dumps(audit(push, morning), ensure_ascii=False, indent=2))
