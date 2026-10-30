"""Read-only historical timing summary from committed push_status.json revisions.

Run locally in a full Git checkout: python scripts/audit_push_history.py
Git history is not a delivery receipt and may omit uncommitted/failed attempts.
"""
import json
import subprocess
from datetime import datetime, time
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def summarize(records):
    """Use the earliest recorded timestamp for each KST date."""
    earliest = {}
    for record in records:
        try:
            sent = datetime.fromisoformat(record["last_sent_at_kst"])
            if sent.tzinfo is None:
                continue
            sent = sent.astimezone(KST)
            day = sent.date().isoformat()
            if record.get("last_sent_date_kst") != day:
                continue
            if day not in earliest or sent < earliest[day]:
                earliest[day] = sent
        except (TypeError, ValueError, KeyError, AttributeError):
            continue
    days = []
    for day, sent in sorted(earliest.items()):
        deadline = datetime.combine(sent.date(), time(7, 30), KST)
        delay = round((sent - deadline).total_seconds())
        days.append({"date_kst": day, "recorded_at_kst": sent.isoformat(),
                     "seconds_from_0730": delay, "on_time_by_record": delay <= 0})
    return {"observed_days": len(days),
            "on_time_days": sum(x["on_time_by_record"] for x in days),
            "on_time_rate_observed_only": (round(sum(x["on_time_by_record"] for x in days) / len(days), 4) if days else None),
            "days": days,
            "limitations": ["Only committed status revisions are counted; missing weekdays are not assumed successful or failed.",
                            "Recorded timestamp can be later than the actual HTTP response.",
                            "Device receipt and duplicate notifications cannot be inferred from this report."]}


def committed_records():
    history = subprocess.run(["git", "log", "--format=%H", "--", "data/push_status.json"],
                             capture_output=True, text=True, check=True)
    for sha in history.stdout.splitlines():
        blob = subprocess.run(["git", "show", f"{sha}:data/push_status.json"],
                              capture_output=True, text=True, check=False)
        if blob.returncode == 0:
            try:
                yield json.loads(blob.stdout)
            except json.JSONDecodeError:
                pass


if __name__ == "__main__":
    print(json.dumps(summarize(committed_records()), ensure_ascii=False, indent=2))
