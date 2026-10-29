"""Regression checks for the 06:30 refresh and 07:30 publication deadline."""
import ast
import datetime
from pathlib import Path
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "morning_brief.py"


def calculate(at_hour, at_minute):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    targets = {"scheduled", "delay_minutes", "deadline", "late"}
    statements = [
        node for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id in targets for target in node.targets)
    ]
    namespace = {
        "now": datetime.datetime(2026, 10, 29, at_hour, at_minute,
                                 tzinfo=datetime.timezone(datetime.timedelta(hours=9))),
        "round": round,
    }
    exec(compile(ast.Module(body=statements, type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace


class MorningDeadlineTests(unittest.TestCase):
    def test_schedule_starts_at_0630(self):
        result = calculate(6, 30)
        self.assertEqual((result["scheduled"].hour, result["scheduled"].minute), (6, 30))
        self.assertEqual(result["delay_minutes"], 0)

    def test_0729_is_on_time(self):
        self.assertFalse(calculate(7, 29)["late"])

    def test_0730_is_on_time(self):
        self.assertFalse(calculate(7, 30)["late"])

    def test_0731_is_late(self):
        self.assertTrue(calculate(7, 31)["late"])

    def test_ten_minute_delay_flag_uses_0730_deadline(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn("'briefing_late_over_10min':(now-deadline).total_seconds()>600", source)
        for hour, minute, expected in [(6, 41, False), (7, 30, False),
                                       (7, 40, False), (7, 41, True)]:
            with self.subTest(hour=hour, minute=minute):
                now = datetime.datetime(2026, 10, 29, hour, minute,
                    tzinfo=datetime.timezone(datetime.timedelta(hours=9)))
                deadline = now.replace(hour=7, minute=30, second=0, microsecond=0)
                self.assertEqual((now-deadline).total_seconds()>600, expected)

    def test_0641_is_not_late(self):
        self.assertFalse(calculate(6, 41)["late"])


if __name__ == "__main__":
    unittest.main()
