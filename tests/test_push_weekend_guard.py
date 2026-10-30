"""Guard against false-positive weekend notification success without network calls."""
import ast
import importlib.util
from datetime import datetime, timezone
from unittest.mock import patch
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

    def test_saturday_execution_fails_before_network_access(self):
        spec = importlib.util.spec_from_file_location("push_briefing_under_test", SOURCE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        saturday = datetime(2026, 10, 31, 0, 30, tzinfo=timezone.utc)
        class FixedDatetime:
            @staticmethod
            def now(tz=None):
                return saturday.astimezone(tz) if tz else saturday
        with patch.object(module, "datetime", FixedDatetime), patch.object(module, "urlopen") as network:
            with self.assertRaisesRegex(RuntimeError, "Weekend"):
                module.main()
            network.assert_not_called()

    def test_sunday_execution_fails_before_network_access(self):
        spec = importlib.util.spec_from_file_location("push_briefing_sunday_test", SOURCE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        sunday = datetime(2026, 11, 1, 0, 30, tzinfo=timezone.utc)
        class FixedDatetime:
            @staticmethod
            def now(tz=None):
                return sunday.astimezone(tz) if tz else sunday
        with patch.object(module, "datetime", FixedDatetime), patch.object(module, "urlopen") as network:
            with self.assertRaisesRegex(RuntimeError, "Weekend"):
                module.main()
            network.assert_not_called()

    def test_weekday_delivery_time_boundaries(self):
        spec = importlib.util.spec_from_file_location("push_briefing_time_test", SOURCE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        from zoneinfo import ZoneInfo
        from unittest.mock import patch
        import os
        kst = ZoneInfo("Asia/Seoul")
        for hour, minute, expected_error in (
            (7, 29, "refusing early notification"),
            (7, 30, "NTFY_TOPIC is not set"),
            (7, 59, "NTFY_TOPIC is not set"),
            (8, 0, "refusing late notification"),
        ):
            with self.subTest(hour=hour, minute=minute):
                fixed = datetime(2026, 11, 2, hour, minute, tzinfo=kst)
                class FixedDatetime:
                    @staticmethod
                    def now(tz=None):
                        return fixed.astimezone(tz) if tz else fixed
                with patch.object(module, "datetime", FixedDatetime), \
                     patch.object(module, "urlopen") as network, \
                     patch.dict(os.environ, {"NTFY_TOPIC": ""}):
                    with self.assertRaisesRegex(RuntimeError, expected_error):
                        module.main()
                    network.assert_not_called()

    def test_workflow_checks_cutoff_before_expensive_refresh(self):
        workflow = (SOURCE.parents[1] / ".github" / "workflows" / "morning_push.yml").read_text(encoding="utf-8")
        cutoff = workflow.index("- name: Fail fast after morning delivery cutoff")
        freshness = workflow.index("- name: Check prepared briefing freshness")
        install = workflow.index("- name: Install dependencies")
        refresh = workflow.index("- name: Refresh market (retry)")
        self.assertLess(cutoff, freshness)
        self.assertLess(cutoff, install)
        self.assertLess(cutoff, refresh)
        self.assertIn("now.weekday() >= 5", workflow)
        self.assertIn("(now.hour, now.minute) >= (8, 0)", workflow)

    def test_push_success_timestamp_is_recorded_only_after_http_success(self):
        workflow = (SOURCE.parents[1] / ".github" / "workflows" / "morning_push.yml").read_text(encoding="utf-8")
        script = SOURCE.read_text(encoding="utf-8")
        self.assertLess(workflow.index("- name: Send push (retry)"),
                        workflow.index("- name: Record successful delivery attempt"))
        self.assertIn("PUSH_HTTP_SUCCEEDED_KST=", script)
        self.assertIn("last_sent_at_kst", workflow)
        self.assertIn("ntfy HTTP success; device receipt not independently verified", workflow)

    def test_schedule_delay_diagnostic_present(self):
        workflow = (SOURCE.parents[1] / ".github" / "workflows" / "morning_push.yml").read_text(encoding="utf-8")
        self.assertIn("MORNING_PUSH_SCHEDULE_DELAY_SECONDS=", workflow)
        self.assertIn("MORNING_PUSH_EXPECTED_UTC=", workflow)
        self.assertIn("MORNING_PUSH_JOB_STARTED_UTC=", workflow)
        self.assertIn("TRIGGER_CRON: ${{ github.event.schedule }}", workflow)


if __name__ == "__main__":
    unittest.main()
