"""Compile embedded Python in GitHub Actions workflows before deployment."""
from pathlib import Path
import re
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = (
    ROOT / ".github/workflows/market.yml",
    ROOT / ".github/workflows/morning-brief.yml",
)


class EmbeddedPythonWorkflowTests(unittest.TestCase):
    def test_all_python_heredocs_compile(self):
        found = 0
        for workflow in WORKFLOWS:
            source = workflow.read_text(encoding="utf-8")
            blocks = re.findall(
                r"(?m)^([ ]*)python - <<'PY'\\s*\\n(.*?)^\\1PY[ ]*$",
                source,
                flags=re.DOTALL | re.MULTILINE,
            )
            self.assertTrue(blocks, f"No embedded Python found in {workflow.name}")
            for indent, body in blocks:
                found += 1
                try:
                    compile(textwrap.dedent(body), str(workflow), "exec")
                except SyntaxError as exc:
                    self.fail(f"{workflow.name} embedded Python syntax error: {exc}")
        self.assertGreaterEqual(found, 2)

    def test_market_publication_requires_consistency(self):
        source = WORKFLOWS[0].read_text(encoding="utf-8")
        self.assertIn("python scripts/check_consistency.py", source)
        self.assertIn("git push origin HEAD:main", source)
        self.assertLess(
            source.index("      - name: Check briefing consistency"),
            source.index("      - name: Commit data files"),
        )


if __name__ == "__main__":
    unittest.main()
