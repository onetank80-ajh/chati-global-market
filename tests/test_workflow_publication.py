"""Regression checks for coordinated briefing publication workflows."""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MARKET = ROOT / ".github/workflows/market.yml"
MORNING = ROOT / ".github/workflows/morning-brief.yml"


class WorkflowPublicationTests(unittest.TestCase):
    def test_both_writers_share_concurrency_group(self):
        groups = []
        for path in (MARKET, MORNING):
            content = path.read_text(encoding="utf-8")
            match = re.search(r"(?m)^\s*group:\s*(chati-[\w-]+)\s*$", content)
            self.assertIsNotNone(match, str(path))
            groups.append(match.group(1))
        self.assertEqual(groups, ["chati-market-update"] * 2)

    def test_market_workflow_reports_fetch_and_publish_outcomes(self):
        content = MARKET.read_text(encoding="utf-8")
        self.assertIn("id: market_fetch", content)
        self.assertIn("id: publish", content)
        self.assertIn("MARKET_FETCH_OUTCOME: ${{ steps.market_fetch.outcome }}", content)
        self.assertIn("PUBLISH_OUTCOME: ${{ steps.publish.outcome }}", content)
        self.assertIn("if: always()", content)

    def test_market_fetch_retries_and_preserves_failure(self):
        content = MARKET.read_text(encoding="utf-8")
        start = content.index("- name: Fetch market snapshot")
        end = content.index("- name: Fetch headlines", start)
        section = content[start:end]
        self.assertIn("for attempt in 1 2 3; do", section)
        self.assertIn("if python scripts/market_update.py; then", section)
        self.assertIn("sleep 20", section)
        self.assertIn("exit 1", section)
        self.assertIn("keeping previous snapshot", section)
        self.assertLess(section.index("if python scripts/market_update.py; then"), section.index("exit 1"))

    def test_market_refresh_requires_both_derived_files(self):
        content = MARKET.read_text(encoding="utf-8")
        self.assertIn("for derived in data/intelligence.json data/morning.json", content)
        self.assertIn('git diff --cached --name-only -- "$derived"', content)
        self.assertIn("refusing partial publish", content)
        self.assertIn("python scripts/check_consistency.py", content)

    def test_frontend_hides_mismatched_morning_snapshot(self):
        page = (ROOT / "index.html").read_text(encoding="utf-8")
        start = page.index("function renderMorning(")
        end = page.index("function renderSectors(", start)
        renderer = page[start:end]
        guard = "if(!Number.isFinite(drift)||Math.abs(drift)>2/60)"
        self.assertIn(guard, renderer)
        self.assertLess(renderer.index(guard), renderer.index("for(const v of"))
        self.assertIn("브리핑 지표를 숨깁니다.", renderer)

    def test_recovery_tests_run_after_sync(self):
        content = MORNING.read_text(encoding="utf-8")
        sync = content.index("- name: Sync latest snapshots")
        tests = content.index("- name: Offline regression tests on synced code before recovery")
        generation = content.index("- name: Refresh derived intelligence")
        self.assertLess(sync, tests)
        self.assertLess(tests, generation)
        self.assertIn("python -m unittest discover -s tests -v", content)

    def test_recovery_checks_consistency_before_and_after_rebase(self):
        content = MORNING.read_text(encoding="utf-8")
        self.assertGreaterEqual(content.count("python scripts/check_consistency.py"), 2)
        self.assertIn("git pull --rebase origin main", content)


if __name__ == "__main__":
    unittest.main()
