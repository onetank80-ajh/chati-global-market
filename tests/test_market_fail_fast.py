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


if __name__ == "__main__":
    unittest.main()
