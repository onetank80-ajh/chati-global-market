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

    def test_market_refresh_requires_both_derived_files(self):
        content = MARKET.read_text(encoding="utf-8")
        self.assertIn("for derived in data/intelligence.json data/morning.json", content)
        self.assertIn('git diff --cached --name-only -- "$derived"', content)
        self.assertIn("refusing partial publish", content)
        self.assertIn("python scripts/check_consistency.py", content)

    def test_recovery_checks_consistency_before_and_after_rebase(self):
        content = MORNING.read_text(encoding="utf-8")
        self.assertGreaterEqual(content.count("python scripts/check_consistency.py"), 2)
        self.assertIn("git pull --rebase origin main", content)


if __name__ == "__main__":
    unittest.main()
