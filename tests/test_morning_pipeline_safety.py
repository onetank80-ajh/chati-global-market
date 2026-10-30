"""Guard against morning workflow regressions that block critical delivery."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def step(source, name):
    marker = "      - name: " + name + "\n"
    if marker not in source:
        raise AssertionError("Missing workflow step: " + name)
    return source.split(marker, 1)[1].split("\n      - name: ", 1)[0]


class MorningPipelineSafetyTests(unittest.TestCase):
    def test_offline_diagnostics_cannot_block_market_refresh(self):
        source = (ROOT / ".github/workflows/market.yml").read_text(encoding="utf-8")
        tests = step(source, "Required scheduling and freshness guard tests")
        self.assertIn("continue-on-error: true", tests)
        self.assertLess(source.index("Required scheduling and freshness guard tests"),
                        source.index("Fetch market snapshot"))
        self.assertNotIn("continue-on-error: true", step(source, "Fetch market snapshot"))
        self.assertNotIn("continue-on-error: true", step(source, "Check briefing consistency"))

    def test_push_has_multiple_premarket_schedules_and_recovery(self):
        source = (ROOT / ".github/workflows/morning_push.yml").read_text(encoding="utf-8")
        for cron in ("20 22 * * 0-4", "23 22 * * 0-4",
                     "25 22 * * 0-4", "28 22 * * 0-4",
                     "40 22 * * 0-4"):
            with self.subTest(cron=cron):
                self.assertIn("cron: '" + cron + "'", source)
        self.assertIn("Diagnose scheduled start delay", source)
        self.assertIn("MORNING_PUSH_SCHEDULE_DELAY_SECONDS=", source)
        self.assertIn("Decide if push already sent today", source)
        self.assertIn("Fail fast after morning delivery cutoff", source)

    def test_push_can_start_from_successful_market_completion(self):
        source = (ROOT / ".github/workflows/morning_push.yml").read_text(encoding="utf-8")
        self.assertIn("workflows: ['Chati Global Market']", source)
        self.assertIn("types: [completed]", source)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", source)
        self.assertIn("group: chati-morning-pipeline", source)
        self.assertIn("cancel-in-progress: false", source)

    def test_ready_briefing_skips_duplicate_market_refresh(self):
        source = (ROOT / ".github/workflows/morning_push.yml").read_text(encoding="utf-8")
        prepared = step(source, "Check prepared briefing freshness")
        refresh = step(source, "Refresh market (retry)")
        self.assertIn("morning.get('market_snapshot_at') == market.get('generated_at_kst')", prepared)
        self.assertIn("steps.prepared.outputs.ready != 'true'", refresh)
        self.assertIn("steps.status.outputs.send == 'true'", refresh)

    def test_http_acknowledgment_is_wired_into_push_status(self):
        workflow = (ROOT / ".github/workflows/morning_push.yml").read_text(encoding="utf-8")
        sender = (ROOT / "scripts/push_briefing.py").read_text(encoding="utf-8")
        send = step(workflow, "Send push (retry)")
        record = step(workflow, "Record successful delivery attempt")
        self.assertIn("PUSH_HTTP_EVIDENCE_PATH: push_http_evidence.json", send)
        self.assertIn("push_http_evidence.json", record)
        self.assertIn("http_succeeded_at_kst", record)
        self.assertIn("status_recorded_at_kst", record)
        self.assertIn("PUSH_HTTP_EVIDENCE_WRITE_FAILED", sender)
        self.assertIn("PUSH_HTTP_SUCCEEDED_KST=", sender)

    def test_push_remains_guarded_by_freshness_and_delivery_window(self):
        source = (ROOT / ".github/workflows/morning_push.yml").read_text(encoding="utf-8")
        self.assertLess(source.index("Decide if push already sent today"),
                        source.index("Send push (retry)"))
        self.assertLess(source.index("Check prepared briefing freshness"),
                        source.index("Send push (retry)"))
        self.assertLess(source.index("Wait until 07:30 KST"),
                        source.index("Send push (retry)"))
        self.assertIn("08:00 KST cutoff", source)
        self.assertIn("GITHUB_STEP_SUMMARY", source)


if __name__ == "__main__":
    unittest.main()
