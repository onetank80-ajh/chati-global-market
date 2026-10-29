"""Exercise market snapshot failure handling without external network calls."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "market_update.py"


class MarketUpdateSafetyTests(unittest.TestCase):
    def run_offline(self, fail_all, fail_symbol=None):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "data").mkdir()
            target = root / "data" / "market.json"
            original = '{"preserved": true}\n'
            target.write_text(original, encoding="utf-8")
            # Supply a local yfinance stub before importing the production script.
            (root / "yfinance.py").write_text("# offline test stub\n", encoding="utf-8")
            driver = root / "driver.py"
            driver.write_text(
                "import importlib.util, sys\n"
                "from pathlib import Path\n"
                "spec=importlib.util.spec_from_file_location('market_update',sys.argv[1])\n"
                "module=importlib.util.module_from_spec(spec)\n"
                "spec.loader.exec_module(module)\n"
                "def fake_fetch(symbol,name,unit):\n"
                "    return {'status':'unavailable'} if sys.argv[2]=='all' or symbol==sys.argv[3] else "
                "{'status':'ok','change_percent':1.0,'market_date':'2026-10-28'}\n"
                "module.fetch=fake_fetch\n"
                "module.main()\n",
                encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(driver), str(SCRIPT), "all" if fail_all else "ok", fail_symbol or "none"],
                cwd=root, capture_output=True, text=True)
            return result, target.read_text(encoding="utf-8")

    def test_all_quotes_unavailable_preserves_previous_file(self):
        result, content = self.run_offline(True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Required market data unavailable: sp500", result.stdout + result.stderr)
        self.assertEqual(content, '{"preserved": true}\n')

    def test_missing_required_sox_preserves_previous_file(self):
        result, content = self.run_offline(False, "^SOX")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Required market data unavailable: sox", result.stdout + result.stderr)
        self.assertEqual(content, '{"preserved": true}\n')

    def test_missing_optional_dow_still_writes_snapshot(self):
        result, content = self.run_offline(False, "^DJI")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(content)["markets"]["dow"]["status"], "unavailable")

    def test_successful_quotes_replace_previous_file(self):
        result, content = self.run_offline(False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        updated = json.loads(content)
        self.assertEqual(updated["markets"]["sox"]["status"], "ok")
        self.assertNotIn("preserved", updated)


if __name__ == "__main__":
    unittest.main()
