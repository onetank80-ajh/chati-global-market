"""Offline freshness regression tests for the news intelligence generator."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class IntelligenceFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "scripts").mkdir()
        (self.root / "data").mkdir()
        shutil.copy2(ROOT / "scripts" / "intelligence_update.py",
                     self.root / "scripts" / "intelligence_update.py")
        self.write("market.json", {"markets": {
            "sp500": {"status": "ok", "change_percent": 0.6, "market_date": "2026-10-27"},
            "sox": {"status": "ok", "change_percent": 1.2, "market_date": "2026-10-27"},
            "usdkrw": {"status": "ok", "change_percent": -0.2, "market_date": "2026-10-28"},
        }})

    def write(self, name, value):
        (self.root / "data" / name).write_text(json.dumps(value), encoding="utf-8")

    def generate(self, news):
        self.write("news.json", news)
        run = subprocess.run(
            [sys.executable, str(self.root / "scripts" / "intelligence_update.py")],
            cwd=self.root, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        return json.loads((self.root / "data" / "intelligence.json").read_text())

    def test_unsafe_article_link_is_not_exposed(self):
        now = datetime.now(timezone.utc).isoformat()
        result = self.generate({"generated_at_utc": now, "items": [
            {"title": "Nvidia semiconductor stocks rise",
             "url": "javascript:alert(1)", "published_at_utc": now}]})
        self.assertEqual(result["headline_count_after"], 1)
        self.assertEqual(result["top_headlines"][0]["url"], "")

    def test_top_level_news_list_does_not_crash(self):
        result = self.generate([{"title": "unexpected top-level list"}])
        self.assertFalse(result["news_snapshot_fresh"])
        self.assertEqual(result["top_headlines"], [])

    def test_top_level_market_list_does_not_crash(self):
        now = datetime.now(timezone.utc).isoformat()
        self.write("market.json", ["unexpected top-level list"])
        result = self.generate({"generated_at_utc": now, "items": []})
        self.assertEqual(result["market_signals"]["sp500"]["status"], "unavailable")

    def test_malformed_market_quotes_are_unavailable(self):
        now = datetime.now(timezone.utc).isoformat()
        self.write("market.json", {"markets": {"sp500": None, "sox": "broken", "usdkrw": []}})
        result = self.generate({"generated_at_utc": now, "items": []})
        for key in ("sp500", "sox", "usdkrw"):
            self.assertEqual(result["market_signals"][key]["status"], "unavailable")

    def test_malformed_market_collection_does_not_crash(self):
        now = datetime.now(timezone.utc).isoformat()
        self.write("market.json", {"markets": []})
        result = self.generate({"generated_at_utc": now, "items": []})
        self.assertEqual(result["market_signals"]["sox"]["status"], "unavailable")

    def test_old_snapshot_does_not_reuse_recent_article(self):
        now = datetime.now(timezone.utc).isoformat()
        result = self.generate({"generated_at_utc": "2020-01-01T00:00:00+00:00",
                                "items": [{"title": "Nvidia semiconductor stocks rise",
                                           "url": "https://example.com/new",
                                           "published_at_utc": now}]})
        self.assertFalse(result["news_snapshot_fresh"])
        self.assertEqual(result["top_headlines"], [])
        self.assertEqual(result["headline_count_after"], 0)
        self.assertTrue(any("뉴스 수집 시각" in s for s in result["cautions"]))

    def test_fresh_snapshot_keeps_fresh_article(self):
        now = datetime.now(timezone.utc).isoformat()
        result = self.generate({"generated_at_utc": now,
                                "items": [{"title": "Nvidia semiconductor stocks rise",
                                           "url": "https://example.com/new",
                                           "published_at_utc": now}]})
        self.assertTrue(result["news_snapshot_fresh"])
        self.assertEqual(result["headline_count_after"], 1)
        self.assertEqual(len(result["top_headlines"]), 1)

    def test_missing_snapshot_time_blocks_news(self):
        now = datetime.now(timezone.utc).isoformat()
        result = self.generate({"items": [{"title": "US stock market advances",
                                           "url": "https://example.com/new",
                                           "published_at_utc": now}]})
        self.assertFalse(result["news_snapshot_fresh"])
        self.assertEqual(result["top_headlines"], [])

    def test_malformed_news_items_do_not_crash(self):
        now = datetime.now(timezone.utc).isoformat()
        result = self.generate({"generated_at_utc": now, "items": [
            None, "invalid", {"title": "Nvidia semiconductor stocks rise",
                              "url": "https://example.com/new",
                              "published_at_utc": now}]})
        self.assertEqual(result["headline_count_after"], 1)

    def test_nontext_headlines_are_excluded(self):
        now = datetime.now(timezone.utc).isoformat()
        result = self.generate({"generated_at_utc": now, "items": [
            {"title": {"unexpected": "object"}, "published_at_utc": now},
            {"title": ["unexpected", "list"], "published_at_utc": now},
            {"title": "Nvidia semiconductor stocks rise", "published_at_utc": now}]})
        self.assertEqual(result["headline_count_after"], 1)
        self.assertEqual(result["top_headlines"][0]["title"], "Nvidia semiconductor stocks rise")

    def test_naive_news_snapshot_blocks_news_without_crashing(self):
        now = datetime.now(timezone.utc)
        result = self.generate({"generated_at_utc": now.replace(tzinfo=None).isoformat(),
                                "items": [{"title": "Nvidia semiconductor stocks rise",
                                           "published_at_utc": now.isoformat()}]})
        self.assertFalse(result["news_snapshot_fresh"])
        self.assertEqual(result["top_headlines"], [])

    def test_naive_article_time_is_excluded(self):
        now = datetime.now(timezone.utc)
        result = self.generate({"generated_at_utc": now.isoformat(),
                                "items": [{"title": "Nvidia semiconductor stocks rise",
                                           "published_at_utc": now.replace(tzinfo=None).isoformat()}]})
        self.assertEqual(result["top_headlines"], [])

    def test_old_article_excluded_even_with_fresh_snapshot(self):
        now = datetime.now(timezone.utc).isoformat()
        result = self.generate({"generated_at_utc": now,
                                "items": [{"title": "Old market article",
                                           "url": "https://example.com/old",
                                           "published_at_utc": "2020-01-01T00:00:00+00:00"}]})
        self.assertTrue(result["news_snapshot_fresh"])
        self.assertEqual(result["top_headlines"], [])


if __name__ == "__main__":
    unittest.main()
