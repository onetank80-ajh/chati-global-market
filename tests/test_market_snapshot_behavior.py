"""Behavioral regression tests for atomic market snapshot updates."""
import json
import os
from pathlib import Path
import tempfile
import unittest
import sys
from unittest.mock import MagicMock, patch

# The recovery workflow runs offline tests without installing yfinance.
# These tests mock fetch(), so the external package is not required.
try:
    import yfinance
except ImportError:
    sys.modules['yfinance'] = MagicMock()

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

    def test_optional_quote_failure_still_saves_required_quotes(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = os.getcwd()
            try:
                os.chdir(tmp)
                def fake_fetch(symbol, name, unit):
                    if symbol == "^DJI":
                        return {"symbol": symbol, "status": "unavailable", "error": "temporary failure"}
                    return {"symbol": symbol, "name": name, "unit": unit,
                            "status": "ok", "change_percent": 0.1,
                            "market_date": "2026-10-28"}
                with patch.object(market_update, "fetch", side_effect=fake_fetch):
                    market_update.main()
                data = json.loads((Path("data") / "market.json").read_text(encoding="utf-8"))
                self.assertEqual(data["markets"]["dow"]["status"], "unavailable")
                self.assertTrue(all(data["markets"][key]["status"] == "ok"
                                    for key in ("sp500", "sox", "usdkrw")))
            finally:
                os.chdir(original)

    def test_failed_atomic_replace_preserves_previous_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data" / "market.json"
            path.parent.mkdir()
            previous = '{"previous": true}\\n'
            path.write_text(previous, encoding="utf-8")
            original = os.getcwd()
            try:
                os.chdir(tmp)
                def fake_fetch(symbol, name, unit):
                    return {"symbol": symbol, "name": name, "unit": unit,
                            "status": "ok", "change_percent": 0.1,
                            "market_date": "2026-10-28"}
                with patch.object(market_update, "fetch", side_effect=fake_fetch):
                    with patch.object(market_update.os, "replace", side_effect=OSError("disk error")):
                        with self.assertRaisesRegex(OSError, "disk error"):
                            market_update.main()
                self.assertEqual(path.read_text(encoding="utf-8"), previous)
                self.assertEqual(list(path.parent.glob(".market-*.json")), [])
            finally:
                os.chdir(original)

    def test_quote_fetch_progress_logs_all_symbols(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = os.getcwd()
            try:
                os.chdir(tmp)
                def fake_fetch(symbol, name, unit):
                    return {"symbol": symbol, "name": name, "unit": unit,
                            "status": "ok", "change_percent": 0.1,
                            "market_date": "2026-10-28"}
                from io import StringIO
                with patch.object(market_update, "fetch", side_effect=fake_fetch):
                    with patch("sys.stdout", new_callable=StringIO) as output:
                        market_update.main()
                logs = output.getvalue()
                for key, (symbol, _, _) in market_update.SYMBOLS.items():
                    self.assertIn(f"Fetching quote: {key} ({symbol})", logs)
                    self.assertIn(f"Quote result: {key} status=ok", logs)
            finally:
                os.chdir(original)

    def test_optional_failure_logs_symbol_and_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = os.getcwd()
            try:
                os.chdir(tmp)
                def fake_fetch(symbol, name, unit):
                    if symbol == "^DJI":
                        return {"symbol": symbol, "status": "unavailable", "error": "provider timeout"}
                    return {"symbol": symbol, "name": name, "unit": unit,
                            "status": "ok", "change_percent": 0.1,
                            "market_date": "2026-10-28"}
                from io import StringIO
                with patch.object(market_update, "fetch", side_effect=fake_fetch):
                    with patch("sys.stdout", new_callable=StringIO) as output:
                        market_update.main()
                self.assertIn("Quote unavailable: dow (^DJI): provider timeout", output.getvalue())
                self.assertTrue((Path("data") / "market.json").exists())
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
