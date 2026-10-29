"""Execute the recovery workflow's actual freshness guard with fixture snapshots."""
import json
import re
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/morning-brief.yml"


class RecoveryMarketFreshnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = WORKFLOW.read_text(encoding="utf-8")
        block = source.split("- name: Recover stale or missing market snapshot", 1)[1]
        block = block.split("- name: Detect out-of-sync market briefing", 1)[0]
        match = re.search(r"if python - <<'PY'\n(.*?)\n          PY", block, re.S)
        if not match:
            raise AssertionError("Recovery freshness Python heredoc missing")
        cls.guard = "\n".join(line[10:] for line in match.group(1).splitlines())

    def check_snapshot(self, age_minutes=15, missing=None, naive=False, malformed=False, bad_close=None):
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder) / "data"
            data.mkdir()
            stamp = datetime.now(timezone.utc) - timedelta(minutes=age_minutes)
            if naive:
                stamp = stamp.replace(tzinfo=None)
            quotes = {key: {"status": "ok", "close": 100.0, "market_date": "2026-10-28"}
                      for key in ("sp500", "sox", "usdkrw")}
            if bad_close is not None:
                quotes["sox"]["close"] = bad_close
            if missing:
                quotes[missing] = {"status": "unavailable"}
            payload = {"generated_at_utc": stamp.isoformat(), "markets": quotes}
            (data / "market.json").write_text(
                "{invalid" if malformed else json.dumps(payload), encoding="utf-8")
            return subprocess.run(
                [sys.executable, "-c", self.guard], cwd=folder,
                capture_output=True, text=True, timeout=10)

    def test_fresh_complete_snapshot_is_accepted(self):
        result = self.check_snapshot()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_old_snapshot_requires_refetch(self):
        self.assertEqual(self.check_snapshot(age_minutes=1440).returncode, 1)

    def test_missing_critical_quotes_require_refetch(self):
        for key in ("sp500", "sox", "usdkrw"):
            with self.subTest(key=key):
                self.assertEqual(self.check_snapshot(missing=key).returncode, 1)

    def test_invalid_close_requires_refetch(self):
        for close in (0, -1, "not-a-number", True):
            with self.subTest(close=close):
                self.assertEqual(self.check_snapshot(bad_close=close).returncode, 1)

    def test_naive_timestamp_requires_refetch(self):
        self.assertEqual(self.check_snapshot(naive=True).returncode, 1)

    def test_malformed_json_requires_refetch(self):
        self.assertEqual(self.check_snapshot(malformed=True).returncode, 1)


if __name__ == "__main__":
    unittest.main()
