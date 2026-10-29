"""Validate UTC cron schedules against intended Korean weekdays."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
KST = timezone(timedelta(hours=9))
CRON = re.compile(r"""cron:\s*['"](\d+)\s+(\d+)\s+\*\s+\*\s+([0-6,-]+)['"]""")


def local_schedule(path):
    source = (ROOT / path).read_text(encoding="utf-8")
    expressions = CRON.findall(source)
    if not expressions:
        raise AssertionError(f"No recognizable cron schedule in {path}")
    sunday = datetime(2026, 10, 25, tzinfo=timezone.utc)
    local_times = []
    for minute, hour, weekdays in expressions:
        days = set()
        for part in weekdays.split(","):
            if "-" in part:
                start, end = map(int, part.split("-"))
                days.update(range(start, end + 1))
            else:
                days.add(int(part))
        for day in days:
            utc = sunday + timedelta(days=day, hours=int(hour), minutes=int(minute))
            local_times.append(utc.astimezone(KST))
    return local_times


class MarketScheduleTests(unittest.TestCase):
    def test_market_refresh_is_0630_0650_0705_kst_weekdays(self):
        times = local_schedule(".github/workflows/market.yml")
        self.assertEqual(len(times), 15)
        self.assertEqual({(t.weekday(), t.hour, t.minute) for t in times},
                         {(day, hour, minute) for day in range(5)
                          for hour, minute in [(6, 30), (6, 50), (7, 5)]})

    def test_repair_checks_are_0715_0830_0930_kst_weekdays(self):
        times = local_schedule(".github/workflows/morning-brief.yml")
        self.assertEqual(len(times), 15)
        self.assertEqual({(t.weekday(), t.hour, t.minute) for t in times},
                         {(day, hour, minute) for day in range(5)
                          for hour, minute in [(7, 15), (8, 30), (9, 30)]})


if __name__ == "__main__":
    unittest.main()
