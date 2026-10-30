"""Guard against false-positive weekend notification success without network calls."""
import ast
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "push_briefing.py"


class WeekendPushGuardTests(unittest.TestCase):
    def test_weekend_guard_raises_instead_of_returning_success(self):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")
        guard = next(node for node in main.body if isinstance(node, ast.If)
                     and isinstance(node.test, ast.Compare)
                     and isinstance(node.test.left, ast.Call)
                     and isinstance(node.test.left.func, ast.Attribute)
                     and node.test.left.func.attr == "weekday")
        self.assertTrue(any(isinstance(stmt, ast.Raise) for stmt in guard.body),
                        "Weekend guard must fail, not return success")
        self.assertFalse(any(isinstance(stmt, ast.Return) for stmt in guard.body))

    def test_schedule_delay_diagnostic_present(self):
        workflow = (SOURCE.parents[1] / ".github" / "workflows" / "morning_push.yml").read_text(encoding="utf-8")
        self.assertIn("MORNING_PUSH_SCHEDULE_DELAY_SECONDS=", workflow)
        self.assertIn("MORNING_PUSH_EXPECTED_UTC=", workflow)
        self.assertIn("MORNING_PUSH_JOB_STARTED_UTC=", workflow)
        self.assertIn("TRIGGER_CRON: ${{ github.event.schedule }}", workflow)


if __name__ == "__main__":
    unittest.main()
