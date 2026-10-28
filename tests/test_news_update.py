"""Offline RSS parser regression tests; no network or Actions trigger."""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from unittest.mock import patch
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import news_update


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit):
        return self.payload[:limit]


class NewsRSSOfflineTests(unittest.TestCase):
    def fetch(self, title, url, date):
        xml = ("<rss><channel><item><title>" + escape(title) +
               "</title><link>" + escape(url) +
               "</link><pubDate>" + escape(date) +
               "</pubDate></item></channel></rss>").encode("utf-8")
        with patch.object(news_update.urllib.request, "urlopen",
                          return_value=FakeResponse(xml)):
            return news_update.get_news("us_market", "test")

    def test_recent_https_article_is_kept(self):
        stamp = format_datetime(datetime.now(timezone.utc) - timedelta(hours=1))
        result = self.fetch("Stocks rise", "https://example.com/story", stamp)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Stocks rise")

    def test_unsafe_article_url_is_rejected(self):
        stamp = format_datetime(datetime.now(timezone.utc) - timedelta(hours=1))
        self.assertEqual(self.fetch("Stocks rise", "javascript:alert(1)", stamp), [])

    def test_stale_article_is_rejected(self):
        stamp = format_datetime(datetime.now(timezone.utc) - timedelta(days=4))
        self.assertEqual(self.fetch("Old headline", "https://example.com/old", stamp), [])

    def test_invalid_date_is_rejected(self):
        self.assertEqual(self.fetch("Stocks rise", "https://example.com/new", "invalid"), [])


if __name__ == "__main__":
    unittest.main()
