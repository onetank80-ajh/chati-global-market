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
                r"(?m)^([ ]*)python - <<'PY'[ ]*\n(.*?)^\1PY[ ]*$",
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


    def test_morning_publication_precedes_optional_work(self):
        source = WORKFLOWS[0].read_text(encoding="utf-8")
        stages = (
            "      - name: Required scheduling and freshness guard tests",
            "      - name: Fetch market snapshot",
            "      - name: Generate v1 intelligence",
            "      - name: Generate morning briefing from fresh snapshots",
            "      - name: Check briefing consistency",
            "      - name: Commit data files",
            "      - name: Fetch headlines (optional, max 15s)",
            "      - name: Generate existing briefing (optional, max 10s)",
            "      - name: Publish optional legacy data",
            "      - name: Offline regression tests (report failures without blocking market refresh)",
        )
        positions = [source.index(stage) for stage in stages]
        self.assertEqual(positions, sorted(positions),
                         "Optional work must not delay the critical morning publication")


if __name__ == "__main__":
    unittest.main()
