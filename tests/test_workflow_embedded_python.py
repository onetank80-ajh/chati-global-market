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
                r"(?m)^([ ]*)(?:if )?python - <<'PY'[ ]*\n(.*?)^\1PY[ ]*$",
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
        self.assertGreaterEqual(found, 5, "Recovery guard and diagnostics must also be compiled")

    def test_recovery_postfetch_checks_real_quote_values(self):
        source = WORKFLOWS[1].read_text(encoding="utf-8")
        verification = source.split(
            "      - name: Verify recovered snapshot before derived generation", 1
        )[1].split("      - name: Detect out-of-sync market briefing", 1)[0]
        self.assertIn('close = quote.get("close")', verification)
        self.assertIn("math.isfinite(close)", verification)
        self.assertIn("close <= 0", verification)
        self.assertIn('quote.get("market_date")', verification)
        self.assertLess(
            source.index("      - name: Verify recovered snapshot before derived generation"),
            source.index("      - name: Refresh derived intelligence"),
        )

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


    def test_critical_publish_stages_only_required_data(self):
        source = WORKFLOWS[0].read_text(encoding="utf-8")
        critical = source.split("      - name: Commit data files", 1)[1].split(
            "      - name: Fetch headlines (optional, max 15s)", 1
        )[0]
        self.assertIn("git add data/market.json data/intelligence.json data/morning.json", critical)
        self.assertNotIn("git add data/news.json", critical)
        self.assertNotIn("git add data/briefing.json", critical)
        self.assertIn("git push origin HEAD:main", critical)

    def test_optional_publish_cannot_block_critical_publish(self):
        source = WORKFLOWS[0].read_text(encoding="utf-8")
        critical = source.index("      - name: Commit data files")
        optional = source.index("      - name: Publish optional legacy data")
        self.assertLess(critical, optional)
        optional_stage = source[optional:source.index(
            "      - name: Offline regression tests", optional
        )]
        self.assertIn("continue-on-error: true", optional_stage)


    def test_recovery_publish_precedes_diagnostic_regressions(self):
        source = WORKFLOWS[1].read_text(encoding="utf-8")
        required = source.index("      - name: Required recovery schedule and freshness guard tests")
        intelligence = source.index("      - name: Refresh derived intelligence from existing JSON snapshots")
        morning = source.index("      - name: Generate morning brief from existing JSON snapshots")
        consistency = source.index("      - name: Check briefing consistency before commit")
        publish = source.index("      - name: Commit updated JSON")
        diagnostic = source.index("      - name: Offline regression tests (diagnostic; do not block validated recovery)")
        self.assertEqual(
            [required, intelligence, morning, consistency, publish, diagnostic],
            sorted([required, intelligence, morning, consistency, publish, diagnostic]),
            "Diagnostic regression must not delay recovery publication",
        )


    def test_market_core_is_independent_of_optional_news(self):
        source = WORKFLOWS[0].read_text(encoding="utf-8")
        publish = source.index("      - name: Commit data files")
        news = source.index("      - name: Fetch headlines (optional, max 15s)")
        legacy = source.index("      - name: Generate existing briefing (optional, max 10s)")
        self.assertLess(publish, news)
        self.assertLess(publish, legacy)
        critical = source[:news]
        self.assertNotIn("python scripts/news_update.py", critical)
        self.assertNotIn("python scripts/briefing_update.py", critical)


    def test_recovery_diagnostics_run_after_failed_repair(self):
        source = WORKFLOWS[1].read_text(encoding="utf-8")
        diagnostic = source.split(
            "      - name: Offline regression tests (diagnostic; do not block validated recovery)", 1
        )[1].split("      - name: Report recovery evidence", 1)[0]
        self.assertIn("if: always() && steps.drift.outputs.repair == 'true'", diagnostic)
        self.assertIn("continue-on-error: true", diagnostic)


if __name__ == "__main__":
    unittest.main()
