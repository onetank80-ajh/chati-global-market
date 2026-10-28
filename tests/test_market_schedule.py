"""Ensure the UTC cron runs at 06:30 KST on Korean weekdays only."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import unittest

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "market.yml"
KST = timezone(timedelta(hours=9))


class MarketScheduleTests(unittest.TestCase):
    def test_cron_maps_to_korean_weekdays(self):
        source = WORKFLOW.read_text(encoding="utf-8")
        match = re.search(r"cron:\\s*['\\\"](\\d+)\\s+(\\d+)\\s+\\*\\s+\\*\\s+([0-6,-]+)['\\\"]", source)
        self.assertIsNotNone(match, "Expected explicit UTC schedule")
        minute, hour = map(int, match.group(1, 2))
        days = set()
        for chunk in match.group(3).split(","):
            if "-" in chunk:
                first, last = map(int, chunk.split("-"))
                days.update(range(first, last + 1))
            else:
                days.add(int(chunk))
        # Sunday 2026-10-25 is cron weekday 0; all UTC schedule days in this week.
        sunday = datetime(2026, 10, 25, tzinfo=timezone.utc)
        local_times = [
            (sunday + timedelta(days=day, hours=hour, minutes=minute)).astimezone(KST)
            for day in sorted(days)
        ]
        self.assertEqual({t.weekday() for t in local_times}, set(range(5)))
        self.assertTrue(all((t.hour, t.minute) == (6, 30) for t in local_times))


if __name__ == "__main__":
    unittest.main()
