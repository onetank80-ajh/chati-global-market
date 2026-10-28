"""Behavioral regression tests for atomic market snapshot updates."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import market_update


class MarketSnapshotTests(unittest.TestCase):
    def test_required_quote_failure_keeps_previous_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous = '{"previous": true}\n'
            path = Path(tmp) / "data" / "market.json"
            path.parent.mkdir()
            path.write_text(previous, encoding="utf-8")
            original = os.getcwd()
            try:
                os.chdir(tmp)
                def fake_fetch(symbol, name, unit):
                    if symbol == "^SOX":
                        return {"symbol": symbol, "status": "unavailable", "error": "provider timeout"}
                    return {"symbol": symbol, "status": "ok", "change_percent": 0.1, "market_date": "2026-10-28"}
                with patch.object(market_update, "fetch", side_effect=fake_fetch):
                    with self.assertRaisesRegex(RuntimeError, "Required market data unavailable"):
                        market_update.main()
                self.assertEqual(path.read_text(encoding="utf-8"), previous)
            finally:
                os.chdir(original)

    def test_success_writes_complete_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = os.getcwd()
            try:
                os.chdir(tmp)
                def fake_fetch(symbol, name, unit):
                    return {"symbol": symbol, "name": name, "unit": unit,
                            "status": "ok", "change_percent": 0.1,
                            "market_date": "2026-10-28"}
                with patch.object(market_update, "fetch", side_effect=fake_fetch):
                    market_update.main()
                data = json.loads((Path("data") / "market.json").read_text(encoding="utf-8"))
                self.assertEqual(set(data["markets"]), set(market_update.SYMBOLS))
                self.assertTrue(all(row["status"] == "ok" for row in data["markets"].values()))
                self.assertTrue(data["generated_at_kst"].endswith("+09:00"))
            finally:
                os.chdir(original)


if __name__ == "__main__":
    unittest.main()
