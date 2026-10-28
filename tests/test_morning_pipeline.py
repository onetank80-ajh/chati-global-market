"""Offline integration tests; run with python -m unittest discover -s tests."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
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
        us_day = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
        fx_day = datetime.now(timezone.utc).date().isoformat()
        self.market = {
            "generated_at_utc": now,
            "generated_at_kst": now,
            "markets": {
                "sp500": {"status": "ok", "change_percent": 0.6, "market_date": us_day},
                "sox": {"status": "ok", "change_percent": 1.2, "market_date": us_day},
                "usdkrw": {"status": "ok", "change_percent": -0.2, "market_date": fx_day},
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

    def test_generation_too_late_after_market_snapshot_blocks_publication(self):
        from datetime import timedelta
        earlier = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        self.market["generated_at_utc"] = earlier
        self.market["generated_at_kst"] = earlier
        self.save_market()
        self.assertEqual(self.run_script("intelligence_update.py").returncode, 0)
        self.assertEqual(self.run_script("morning_brief.py").returncode, 0)
        result = self.run_script("check_consistency.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("generation time outside market snapshot window", result.stdout + result.stderr)

    def test_old_trading_date_blocks_publication(self):
        self.market["markets"]["sox"]["market_date"] = (datetime.now(timezone.utc) - timedelta(days=20)).date().isoformat()
        self.save_market()
        self.assertEqual(self.run_script("intelligence_update.py").returncode, 0)
        self.assertEqual(self.run_script("morning_brief.py").returncode, 0)
        result = self.run_script("check_consistency.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stale or future sox market date", result.stdout + result.stderr)

    def test_future_trading_date_blocks_publication(self):
        self.market["markets"]["sox"]["market_date"] = (datetime.now(timezone.utc) + timedelta(days=10)).date().isoformat()
        self.save_market()
        self.assertEqual(self.run_script("intelligence_update.py").returncode, 0)
        self.assertEqual(self.run_script("morning_brief.py").returncode, 0)
        result = self.run_script("check_consistency.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stale or future sox market date", result.stdout + result.stderr)

    def test_invalid_market_date_blocks_publication(self):
        self.market["markets"]["sox"]["market_date"] = "2026-02-30"
        self.save_market()
        self.assertEqual(self.run_script("intelligence_update.py").returncode, 0)
        self.assertEqual(self.run_script("morning_brief.py").returncode, 0)
        result = self.run_script("check_consistency.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid sox market date", result.stdout + result.stderr)

    def test_matching_snapshot_passes_even_when_fx_date_differs(self):
        self.assertEqual(self.run_script("morning_brief.py").returncode, 0)
        result = self.run_script("check_consistency.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_forged_fresh_flag_cannot_publish_old_market_snapshot(self):
        self.assertEqual(self.run_script("morning_brief.py").returncode, 0)
        old = "2020-01-01T00:00:00+00:00"
        self.market["generated_at_utc"] = old
        self.market["generated_at_kst"] = old
        self.save_market()
        morning = json.loads((self.root / "data" / "morning.json").read_text())
        morning["market_snapshot_at"] = old
        morning["market_snapshot_fresh"] = True
        self.write("morning.json", morning)
        result = self.run_script("check_consistency.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("market snapshot is stale", result.stdout + result.stderr)

    def test_old_intelligence_generation_is_rejected(self):
        self.assertEqual(self.run_script("morning_brief.py").returncode, 0)
        intelligence = json.loads((self.root / "data" / "intelligence.json").read_text())
        intelligence["generated_at_utc"] = "2020-01-01T00:00:00+00:00"
        self.write("intelligence.json", intelligence)
        result = self.run_script("check_consistency.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("intelligence generation time outside", result.stdout + result.stderr)

    def test_old_morning_generation_is_rejected(self):
        self.assertEqual(self.run_script("morning_brief.py").returncode, 0)
        morning = json.loads((self.root / "data" / "morning.json").read_text())
        morning["generated_at_kst"] = "2020-01-01T00:00:00+00:00"
        self.write("morning.json", morning)
        result = self.run_script("check_consistency.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("morning generation time outside", result.stdout + result.stderr)

    def test_mixed_us_trading_dates_block_publication(self):
        self.market["markets"]["sox"]["market_date"] = "2026-10-26"
        self.save_market()
        self.assertEqual(self.run_script("intelligence_update.py").returncode, 0)
        self.assertEqual(self.run_script("morning_brief.py").returncode, 0)
        result = self.run_script("check_consistency.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("different trading dates", result.stdout + result.stderr)

    def test_changed_market_snapshot_fails(self):
        self.assertEqual(self.run_script("morning_brief.py").returncode, 0)
        self.market["markets"]["sox"]["change_percent"] = -1.0
        self.save_market()
        result = self.run_script("check_consistency.py")
        self.assertNotEqual(result.returncode, 0)

    def test_missing_quote_market_date_blocks_publication(self):
        self.market["markets"]["sox"]["market_date"] = None
        self.save_market()
        self.assertEqual(self.run_script("intelligence_update.py").returncode, 0)
        self.assertEqual(self.run_script("morning_brief.py").returncode, 0)
        result = self.run_script("check_consistency.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid sox market date", result.stdout + result.stderr)

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

    def test_boolean_intelligence_signal_blocks_publication(self):
        self.assertEqual(self.run_script("morning_brief.py").returncode, 0)
        intelligence = json.loads((self.root / "data" / "intelligence.json").read_text())
        intelligence["market_signals"]["sox"]["change_percent"] = True
        self.write("intelligence.json", intelligence)
        result = self.run_script("check_consistency.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid intelligence sox percentage", result.stdout + result.stderr)

    def test_boolean_morning_indicator_blocks_publication(self):
        self.assertEqual(self.run_script("morning_brief.py").returncode, 0)
        morning = json.loads((self.root / "data" / "morning.json").read_text())
        for row in morning["indicators"]:
            if row["name"] == "반도체":
                row["change_percent"] = True
        self.write("morning.json", morning)
        result = self.run_script("check_consistency.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid morning sox percentage", result.stdout + result.stderr)

    def test_nonfinite_intelligence_snapshot_delta_blocks_publication(self):
        self.assertEqual(self.run_script("morning_brief.py").returncode, 0)
        intelligence = json.loads((self.root / "data" / "intelligence.json").read_text())
        intelligence["market_snapshot_at"] = "9999-12-31T23:59:59+00:00"
        self.write("intelligence.json", intelligence)
        result = self.run_script("check_consistency.py")
        self.assertNotEqual(result.returncode, 0)

    def test_malformed_top_level_morning_blocks_publication(self):
        self.assertEqual(self.run_script("morning_brief.py").returncode, 0)
        self.write("morning.json", [])
        result = self.run_script("check_consistency.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FAIL: malformed market or morning document", result.stdout + result.stderr)

    def test_malformed_top_level_intelligence_blocks_publication(self):
        self.assertEqual(self.run_script("morning_brief.py").returncode, 0)
        self.write("intelligence.json", [])
        result = self.run_script("check_consistency.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FAIL: malformed intelligence document", result.stdout + result.stderr)

    def test_duplicate_morning_indicators_block_publication(self):
        self.assertEqual(self.run_script("morning_brief.py").returncode, 0)
        morning = json.loads((self.root / "data" / "morning.json").read_text())
        morning["indicators"].append(dict(morning["indicators"][0]))
        self.write("morning.json", morning)
        result = self.run_script("check_consistency.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate morning indicator names", result.stdout + result.stderr)

    def test_nontext_morning_indicator_name_blocks_publication(self):
        self.assertEqual(self.run_script("morning_brief.py").returncode, 0)
        morning = json.loads((self.root / "data" / "morning.json").read_text())
        morning["indicators"][0]["name"] = ["invalid"]
        self.write("morning.json", morning)
        result = self.run_script("check_consistency.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("malformed morning indicator name", result.stdout + result.stderr)

    def test_duplicate_morning_indicators_block_publication(self):
        self.assertEqual(self.run_script("morning_brief.py").returncode, 0)
        morning = json.loads((self.root / "data" / "morning.json").read_text())
        morning["indicators"].append(dict(morning["indicators"][0]))
        self.write("morning.json", morning)
        result = self.run_script("check_consistency.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate morning indicators", result.stdout + result.stderr)

    def test_malformed_morning_indicators_block_publication_cleanly(self):
        self.assertEqual(self.run_script("morning_brief.py").returncode, 0)
        morning = json.loads((self.root / "data" / "morning.json").read_text())
        morning["indicators"] = [None]
        self.write("morning.json", morning)
        result = self.run_script("check_consistency.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FAIL: malformed morning indicators", result.stdout + result.stderr)

    def test_malformed_intelligence_signals_block_publication_cleanly(self):
        self.assertEqual(self.run_script("morning_brief.py").returncode, 0)
        intelligence = json.loads((self.root / "data" / "intelligence.json").read_text())
        intelligence["market_signals"] = []
        self.write("intelligence.json", intelligence)
        result = self.run_script("check_consistency.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FAIL: malformed intelligence signals", result.stdout + result.stderr)

    def test_nonobject_input_roots_do_not_crash_briefing(self):
        self.write("market.json", [])
        self.write("news.json", None)
        self.write("intelligence.json", "invalid")
        result = self.run_script("morning_brief.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        morning = json.loads((self.root / "data" / "morning.json").read_text())
        self.assertEqual(morning["indicators"], [])
        self.assertEqual(morning["headlines"], [])
        self.assertEqual(morning["sectors"], [])

    def test_malformed_market_quote_does_not_crash_briefing(self):
        self.market["markets"]["sox"] = None
        self.save_market()
        result = self.run_script("morning_brief.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        morning = json.loads((self.root / "data" / "morning.json").read_text())
        self.assertNotIn("반도체", [row["name"] for row in morning["indicators"]])

    def test_malformed_market_collection_does_not_crash_briefing(self):
        self.market["markets"] = []
        self.save_market()
        result = self.run_script("morning_brief.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        morning = json.loads((self.root / "data" / "morning.json").read_text())
        self.assertEqual(morning["indicators"], [])

    def test_snapshot_just_over_twelve_hours_is_stale(self):
        from datetime import timedelta
        old = (datetime.now(timezone.utc) - timedelta(hours=12, seconds=2)).isoformat()
        self.market["generated_at_utc"] = old
        self.market["generated_at_kst"] = old
        self.save_market()
        result = self.run_script("morning_brief.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        morning = json.loads((self.root / "data" / "morning.json").read_text())
        self.assertFalse(morning["market_snapshot_fresh"])

    def test_blank_article_title_is_not_published(self):
        now = datetime.now(timezone.utc).isoformat()
        self.write("news.json", {"generated_at_utc": now, "items": [
            {"title": "   ", "url": "https://example.com/blank", "published_at_utc": now}]})
        result = self.run_script("morning_brief.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        morning = json.loads((self.root / "data" / "morning.json").read_text())
        self.assertEqual(morning["headlines"], [])

    def test_malformed_https_news_links_are_hidden(self):
        now = datetime.now(timezone.utc).isoformat()
        self.write("news.json", {"generated_at_utc": now, "items": [
            {"title": "Bad missing host", "url": "https://", "published_at_utc": now},
            {"title": "Bad whitespace", "url": "https://example.com/a b", "published_at_utc": now},
            {"title": "Valid market story", "url": "https://example.com/market", "published_at_utc": now},
        ]})
        result = self.run_script("morning_brief.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        morning = json.loads((self.root / "data" / "morning.json").read_text())
        self.assertEqual([row["title"] for row in morning["headlines"]], ["Valid market story"])

    def test_nontext_news_source_is_normalized(self):
        now = datetime.now(timezone.utc).isoformat()
        self.write("news.json", {"generated_at_utc": now, "items": [
            {"title": "Market news", "url": "https://example.com/article",
             "source": {"unexpected": "object"}, "published_at_utc": now}]})
        result = self.run_script("morning_brief.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        morning = json.loads((self.root / "data" / "morning.json").read_text())
        self.assertEqual(len(morning["headlines"]), 1)
        self.assertEqual(morning["headlines"][0]["source"], "")

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

    def test_extreme_intelligence_timestamp_hides_sectors(self):
        intelligence = json.loads((self.root / "data" / "intelligence.json").read_text())
        intelligence["market_snapshot_at"] = "9999-12-31T23:59:59+00:00"
        intelligence["sectors"] = [{"name": "out-of-range sector"}]
        self.write("intelligence.json", intelligence)
        result = self.run_script("morning_brief.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        morning = json.loads((self.root / "data" / "morning.json").read_text())
        self.assertEqual(morning["sectors"], [])

    def test_naive_intelligence_timestamp_hides_sectors(self):
        intelligence = json.loads((self.root / "data" / "intelligence.json").read_text())
        intelligence["market_snapshot_at"] = "2026-10-28T07:00:00"
        intelligence["sectors"] = [{"name": "unsafe sector"}]
        self.write("intelligence.json", intelligence)
        result = self.run_script("morning_brief.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        morning = json.loads((self.root / "data" / "morning.json").read_text())
        self.assertEqual(morning["sectors"], [])
        self.assertTrue(any("업종 분석" in warning for warning in morning["warnings"]))

    def test_stale_intelligence_sectors_hidden_from_morning(self):
        intelligence = json.loads((self.root / "data" / "intelligence.json").read_text())
        intelligence["generated_at_utc"] = "2020-01-01T00:00:00+00:00"
        intelligence["sectors"] = [{"name": "stale sector"}]
        self.write("intelligence.json", intelligence)
        self.assertEqual(self.run_script("morning_brief.py").returncode, 0)
        morning = json.loads((self.root / "data" / "morning.json").read_text())
        self.assertEqual(morning["sectors"], [])
        self.assertTrue(any("업종 분석" in w for w in morning["warnings"]))

    def test_boolean_intelligence_signal_hides_sectors(self):
        intelligence = json.loads((self.root / "data" / "intelligence.json").read_text())
        self.market["markets"]["sp500"]["change_percent"] = 1
        self.save_market()
        intelligence["market_signals"]["sp500"]["change_percent"] = True
        intelligence["sectors"] = [{"name": "boolean signal sector"}]
        self.write("intelligence.json", intelligence)
        result = self.run_script("morning_brief.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        morning = json.loads((self.root / "data" / "morning.json").read_text())
        self.assertEqual(morning["sectors"], [])

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
