"""Offline integration tests; run with python -m unittest discover -s tests."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ("morning_brief.py", "check_consistency.py", "intelligence_update.py")


class MorningPipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "scripts").mkdir()
        (self.root / "data").mkdir()
        for script in SCRIPTS:
            shutil.copy2(ROOT / "scripts" / script, self.root / "scripts" / script)
        now = datetime.now(timezone.utc).isoformat()
        self.market = {
            "generated_at_utc": now,
            "generated_at_kst": now,
            "markets": {
                "sp500": {"status": "ok", "change_percent": 0.6, "market_date": "2026-10-27"},
                "sox": {"status": "ok", "change_percent": 1.2, "market_date": "2026-10-27"},
                "usdkrw": {"status": "ok", "change_percent": -0.2, "market_date": "2026-10-28"},
            },
        }
        self.save_market()
        self.write("news.json", {"items": []})
        self.assertEqual(self.run_script("intelligence_update.py").returncode, 0)

    def write(self, name, value):
        (self.root / "data" / name).write_text(json.dumps(value), encoding="utf-8")

    def save_market(self):
        self.write("market.json", self.market)

    def run_script(self, name):
        return subprocess.run(
            [sys.executable, str(self.root / "scripts" / name)],
            cwd=self.root, capture_output=True, text=True,
        )

    def test_matching_snapshot_passes_even_when_fx_date_differs(self):
        self.assertEqual(self.run_script("morning_brief.py").returncode, 0)
        result = self.run_script("check_consistency.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_changed_market_snapshot_fails(self):
        self.assertEqual(self.run_script("morning_brief.py").returncode, 0)
        self.market["markets"]["sox"]["change_percent"] = -1.0
        self.save_market()
        result = self.run_script("check_consistency.py")
        self.assertNotEqual(result.returncode, 0)

    def test_missing_required_quote_blocks_publication(self):
        self.market["markets"]["sox"] = {"status": "unavailable"}
        self.save_market()
        self.assertEqual(self.run_script("morning_brief.py").returncode, 0)
        result = self.run_script("check_consistency.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("required sox quote unavailable", result.stdout + result.stderr)

    def test_naive_intelligence_snapshot_blocks_publication(self):
        self.assertEqual(self.run_script("morning_brief.py").returncode, 0)
        intelligence = json.loads((self.root / "data" / "intelligence.json").read_text())
        intelligence["market_snapshot_at"] = "2026-10-28T07:00:00"
        self.write("intelligence.json", intelligence)
        result = self.run_script("check_consistency.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing timezone", result.stdout + result.stderr)

    def test_snapshot_timestamp_mismatch_blocks_publication(self):
        self.assertEqual(self.run_script("morning_brief.py").returncode, 0)
        morning = json.loads((self.root / "data" / "morning.json").read_text())
        morning["market_snapshot_at"] = "2020-01-01T00:00:00+00:00"
        self.write("morning.json", morning)
        result = self.run_script("check_consistency.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("different market snapshot", result.stdout + result.stderr)

    def test_malformed_news_list_does_not_crash(self):
        now = datetime.now(timezone.utc).isoformat()
        self.write("news.json", {"generated_at_utc": now, "items": {"unexpected": "object"}})
        result = self.run_script("morning_brief.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        morning = json.loads((self.root / "data" / "morning.json").read_text())
        self.assertEqual(morning["headlines"], [])

    def test_timezone_naive_market_timestamp_is_stale(self):
        self.market["generated_at_utc"] = "2026-10-28T07:00:00"
        self.market["generated_at_kst"] = "2026-10-28T07:00:00"
        self.save_market()
        result = self.run_script("morning_brief.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        morning = json.loads((self.root / "data" / "morning.json").read_text())
        self.assertFalse(morning["market_snapshot_fresh"])
        self.assertIsNone(morning["market_snapshot_age_hours"])

    def test_stale_news_is_not_republished(self):
        self.write("news.json", {
            "generated_at_utc": "2020-01-01T00:00:00+00:00",
            "items": [{"title": "Old headline", "url": "https://example.com/old",
                       "published_at_utc": "2020-01-01T00:00:00+00:00"}],
        })
        self.assertEqual(self.run_script("morning_brief.py").returncode, 0)
        morning = json.loads((self.root / "data" / "morning.json").read_text())
        self.assertFalse(morning["news_snapshot_fresh"])
        self.assertEqual(morning["headlines"], [])
        self.assertTrue(any("뉴스 수집 시각" in w for w in morning["warnings"]))

    def test_recent_news_keeps_only_recent_articles(self):
        now = datetime.now(timezone.utc).isoformat()
        self.write("news.json", {
            "generated_at_utc": now,
            "items": [
                {"title": "Recent", "url": "https://example.com/new", "published_at_utc": now},
                {"title": "Old", "url": "https://example.com/old",
                 "published_at_utc": "2020-01-01T00:00:00+00:00"},
            ],
        })
        self.assertEqual(self.run_script("morning_brief.py").returncode, 0)
        morning = json.loads((self.root / "data" / "morning.json").read_text())
        self.assertTrue(morning["news_snapshot_fresh"])
        self.assertEqual([h["title"] for h in morning["headlines"]], ["Recent"])

    def test_changed_intelligence_snapshot_blocks_publication(self):
        self.assertEqual(self.run_script("morning_brief.py").returncode, 0)
        intelligence = json.loads((self.root / "data" / "intelligence.json").read_text())
        intelligence["market_snapshot_at"] = "2020-01-01T00:00:00+00:00"
        self.write("intelligence.json", intelligence)
        result = self.run_script("check_consistency.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("intelligence uses different market snapshot",
                      result.stdout + result.stderr)

    def test_changed_intelligence_quote_blocks_publication(self):
        self.assertEqual(self.run_script("morning_brief.py").returncode, 0)
        intelligence = json.loads((self.root / "data" / "intelligence.json").read_text())
        intelligence["market_signals"]["sox"]["change_percent"] = -99.0
        self.write("intelligence.json", intelligence)
        result = self.run_script("check_consistency.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("intelligence sox mismatch", result.stdout + result.stderr)

    def test_matching_intelligence_sectors_are_kept(self):
        intelligence = json.loads((self.root / "data" / "intelligence.json").read_text())
        intelligence["sectors"] = [{"name": "current sector"}]
        self.write("intelligence.json", intelligence)
        result = self.run_script("morning_brief.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        morning = json.loads((self.root / "data" / "morning.json").read_text())
        self.assertEqual(morning["sectors"], [{"name": "current sector"}])

    def test_stale_intelligence_sectors_hidden_from_morning(self):
        intelligence = json.loads((self.root / "data" / "intelligence.json").read_text())
        intelligence["generated_at_utc"] = "2020-01-01T00:00:00+00:00"
        intelligence["sectors"] = [{"name": "stale sector"}]
        self.write("intelligence.json", intelligence)
        self.assertEqual(self.run_script("morning_brief.py").returncode, 0)
        morning = json.loads((self.root / "data" / "morning.json").read_text())
        self.assertEqual(morning["sectors"], [])
        self.assertTrue(any("업종 분석" in w for w in morning["warnings"]))

    def test_mismatched_intelligence_sectors_hidden_from_morning(self):
        intelligence = json.loads((self.root / "data" / "intelligence.json").read_text())
        intelligence["market_signals"]["sox"]["change_percent"] = -10
        intelligence["sectors"] = [{"name": "mismatched sector"}]
        self.write("intelligence.json", intelligence)
        self.assertEqual(self.run_script("morning_brief.py").returncode, 0)
        morning = json.loads((self.root / "data" / "morning.json").read_text())
        self.assertEqual(morning["sectors"], [])

    def test_nonfinite_quote_does_not_publish(self):
        self.market["markets"]["sox"]["change_percent"] = float("nan")
        self.save_market()
        self.assertEqual(self.run_script("morning_brief.py").returncode, 0)
        result = self.run_script("check_consistency.py")
        self.assertNotEqual(result.returncode, 0)
        morning = json.loads((self.root / "data" / "morning.json").read_text())
        self.assertEqual(len(morning["indicators"]), 2)


if __name__ == "__main__":
    unittest.main()
