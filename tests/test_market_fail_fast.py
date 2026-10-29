"""Required quote failures must stop optional requests and preserve old data."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/market_update.py"


class MarketFailFastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # No network or yfinance installation required for this offline test.
        with patch.dict(sys.modules, {"yfinance": types.ModuleType("yfinance")}):
            spec = importlib.util.spec_from_file_location("chati_market_update_test", SCRIPT)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            cls.module = module

    def test_required_quote_failure_skips_optional_quotes_and_write(self):
        requested = []
        def fake_fetch(symbol, name, unit):
            requested.append(symbol)
            if symbol == "^SOX":
                return {"symbol": symbol, "status": "unavailable", "error": "provider down"}
            return {"symbol": symbol, "status": "ok"}
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(self.module, "fetch", side_effect=fake_fetch):
                # main() uses a relative data path, so isolate process cwd.
                import os
                old = os.getcwd()
                try:
                    os.chdir(tmp)
                    with self.assertRaisesRegex(RuntimeError, "sox"):
                        self.module.main()
                finally:
                    os.chdir(old)
            self.assertEqual(requested, ["^GSPC", "^SOX"])
            self.assertFalse((Path(tmp) / "data/market.json").exists())


    def test_all_required_failures_stop_before_optional_quotes(self):
        required = ("^GSPC", "^SOX", "KRW=X")
        optional = {"^IXIC", "^DJI"}
        for failing_symbol in required:
            with self.subTest(failing_symbol=failing_symbol):
                requested = []

                def fake_fetch(symbol, name, unit):
                    requested.append(symbol)
                    if symbol == failing_symbol:
                        return {"symbol": symbol, "status": "unavailable", "error": "simulated outage"}
                    return {"symbol": symbol, "status": "ok"}

                with tempfile.TemporaryDirectory() as tmp:
                    with patch.object(self.module, "fetch", side_effect=fake_fetch):
                        import os
                        old = os.getcwd()
                        try:
                            os.chdir(tmp)
                            with self.assertRaisesRegex(RuntimeError, "Required market data unavailable"):
                                self.module.main()
                        finally:
                            os.chdir(old)
                    self.assertEqual(requested, list(required[:required.index(failing_symbol) + 1]))
                    self.assertFalse(optional.intersection(requested))
                    self.assertFalse((Path(tmp) / "data/market.json").exists())

    def test_optional_failure_keeps_valid_required_snapshot(self):
        import json
        import os
        requested = []

        def fake_fetch(symbol, name, unit):
            requested.append(symbol)
            if symbol == "^IXIC":
                return {"symbol": symbol, "status": "unavailable", "error": "simulated outage"}
            return {"symbol": symbol, "status": "ok", "market_date": "2026-10-28",
                    "change_percent": 0.5}

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(self.module, "fetch", side_effect=fake_fetch):
                old = os.getcwd()
                try:
                    os.chdir(tmp)
                    self.module.main()
                finally:
                    os.chdir(old)
            output = json.loads((Path(tmp) / "data/market.json").read_text(encoding="utf-8"))
            self.assertEqual(requested, ["^GSPC", "^SOX", "KRW=X", "^IXIC", "^DJI"])
            self.assertEqual(output["markets"]["nasdaq"]["status"], "unavailable")
            for key in ("sp500", "sox", "usdkrw"):
                self.assertEqual(output["markets"][key]["status"], "ok")


if __name__ == "__main__":
    unittest.main()
