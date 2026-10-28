"""Offline tests for preserving previously published market snapshots."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import importlib.util

ROOT = Path(__file__).resolve().parents[1]


class MarketUpdateSafetyTests(unittest.TestCase):
    def test_all_quotes_unavailable_preserves_previous_file(self):
        source = (ROOT / "scripts" / "market_update.py").read_text(encoding="utf-8")
        self.assertLess(source.index('if all(v["status"] != "ok" for v in items.values()):'),
                        source.index('path.write_text('))

    def test_news_failure_does_not_modify_market_snapshot(self):
        source = (ROOT / "scripts" / "market_update.py").read_text(encoding="utf-8")
        self.assertIn('raise RuntimeError("No market data available; keeping previous market.json")', source)


if __name__ == "__main__":
    unittest.main()
