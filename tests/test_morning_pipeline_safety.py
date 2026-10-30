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
