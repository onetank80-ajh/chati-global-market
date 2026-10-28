"""Verify that the mobile app's inline JavaScript parses before data publication."""
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class MobileJavaScriptSyntaxTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js is not installed")
    def test_inline_scripts_parse(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        scripts = re.findall(r"<script\b[^>]*>([\s\S]*?)</script>", html, re.IGNORECASE)
        self.assertTrue(scripts, "No inline JavaScript found in index.html")
        with tempfile.TemporaryDirectory() as tmp:
            for i, script in enumerate(scripts):
                path = Path(tmp) / f"inline_{i}.js"
                path.write_text(script, encoding="utf-8")
                result = subprocess.run(["node", "--check", str(path)],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0,
                                 f"Inline script {i + 1}: {result.stderr}")


if __name__ == "__main__":
    unittest.main()
