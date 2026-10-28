"""Offline RSS URL validation tests; no network requests."""
import importlib.util
import io
import unittest
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "news_update.py"
spec = importlib.util.spec_from_file_location("chati_news_update", SCRIPT)
news = importlib.util.module_from_spec(spec)
spec.loader.exec_module(news)


class NewsLinkSafetyTests(unittest.TestCase):
    def test_malformed_https_links_are_excluded(self):
        stamp = format_datetime(datetime.now(timezone.utc))
        urls = ["https://", "https://example.com/ok", "https://exa mple.com/bad", "http://example.com/no"]
        xml = "<rss><channel>" + "".join(
            "<item><title>Market news</title><link>" + url + "</link><pubDate>" + stamp + "</pubDate></item>"
            for url in urls
        ) + "</channel></rss>"
        with patch.object(news.urllib.request, "urlopen", return_value=io.BytesIO(xml.encode("utf-8"))):
            rows = news.get_news("us_market", "stocks")
        self.assertEqual([row["url"] for row in rows], ["https://example.com/ok"])


if __name__ == "__main__":
    unittest.main()
