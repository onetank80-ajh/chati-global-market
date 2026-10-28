"""Offline RSS date filtering tests with mocked HTTP response."""
import unittest
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from unittest.mock import patch
from scripts.news_update import get_news


class FakeResponse:
    def __init__(self, body):
        self.body = body
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, limit):
        return self.body[:limit]


class NewsDateTests(unittest.TestCase):
    def test_stale_first_eight_do_not_hide_later_recent_article(self):
        now = datetime.now(timezone.utc)
        old = format_datetime(now - timedelta(days=5))
        fresh = format_datetime(now - timedelta(hours=2))
        items = "".join(
            "<item><title>Old %d</title><link>https://example.org/%d</link><pubDate>%s</pubDate></item>" % (i, i, old)
            for i in range(8)
        )
        items += "<item><title>Recent</title><link>https://example.org/recent</link><pubDate>%s</pubDate></item>" % fresh
        xml = ("<rss><channel>" + items + "</channel></rss>").encode()
        with patch("scripts.news_update.urllib.request.urlopen", return_value=FakeResponse(xml)):
            result = get_news("us_market", "test")
        self.assertEqual([row["title"] for row in result], ["Recent"])

    def test_only_recent_timezone_aware_headline_is_kept(self):
        now = datetime.now(timezone.utc)
        dates = [
            format_datetime(now - timedelta(hours=2)),
            format_datetime(now - timedelta(days=5)),
            format_datetime(now + timedelta(days=2)),
            (now - timedelta(hours=1)).strftime("%a, %d %b %Y %H:%M:%S"),
        ]
        items = "".join(
            "<item><title>News %d</title><link>https://example.org/%d</link><pubDate>%s</pubDate></item>" % (i, i, date)
            for i, date in enumerate(dates)
        )
        xml = ("<rss><channel>" + items + "</channel></rss>").encode()
        with patch("scripts.news_update.urllib.request.urlopen", return_value=FakeResponse(xml)):
            result = get_news("us_market", "test")
        self.assertEqual([row["title"] for row in result], ["News 0"])


if __name__ == "__main__":
    unittest.main()
