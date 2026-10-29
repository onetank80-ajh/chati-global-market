"""Guard the consistency-check recovery window against schedule regressions."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts" / "check_consistency.py"


class RecoveryWindowTests(unittest.TestCase):
    def test_generation_window_covers_delayed_0930_recovery(self):
        tree = ast.parse(CHECKER.read_text(encoding="utf-8"))
        candidates = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name) and node.left.id == "generation_age":
                for operator, comparator in zip(node.ops, node.comparators):
                    if isinstance(operator, ast.Gt):
                        try:
                            candidates.append(ast.literal_eval(comparator))
                        except (ValueError, TypeError):
                            if isinstance(comparator, ast.BinOp) and isinstance(comparator.op, ast.Mult):
                                candidates.append(ast.literal_eval(comparator.left) * ast.literal_eval(comparator.right))
        self.assertIn(10800, candidates, "Delayed recovery must allow 3 hours from market snapshot")

    def test_market_freshness_guard_remains_12_hours(self):
        source = CHECKER.read_text(encoding="utf-8")
        self.assertIn("not 0 <= market_age_hours <= 12", source)


if __name__ == "__main__":
    unittest.main()
