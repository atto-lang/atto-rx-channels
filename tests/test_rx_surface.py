#!/usr/bin/env python3
"""Static Rx contract checks only. NEVER substitutes for Oreslang compiler execution."""
import re
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
# Infer the model from source; exact-tree CI may use a renamed checkout.
SOURCE = (ROOT / "src/rx.ores").read_text()
if "pub subscribe(Fnc<T, bool> on_next): int" in SOURCE:
    KIND = "callbacks"
elif "fnc marked(Channel<bool> marker)" in SOURCE:
    KIND = "channels"
elif "dispose_once(mut self)()" in SOURCE:
    KIND = "pull"
else:
    raise AssertionError("Unrecognized Rx implementation")
EXPECTED = {"pull": "8\n10\ntrue\ntrue",
            "channels": "8\n10\ntrue\ntrue",
            "callbacks": "5\n0"}
class RxStaticContracts(unittest.TestCase):
    def test_model_classifier_is_checkout_path_independent(self):
        self.assertIn(KIND, EXPECTED)

    def test_locked_compiler_is_exact_sha(self):
        self.assertRegex((ROOT / "compiler.lock").read_text().strip(), r"\A[0-9a-f]{40}\Z")

    def test_skip_has_eager_nonnegative_guard(self):
        src = (ROOT / "src/rx.ores").read_text()
        start = src.index("class SkipObservable<T>")
        end = src.index("pub fnc skip<T>", start)
        body = src[start:end]
        self.assertIn("if count < 0; then", body)
        self.assertIn('Err("skip count must be nonnegative")', body)

    def test_take_rejects_negative_count_during_operator_creation(self):
        src = (ROOT / "src/rx.ores").read_text()
        start = src.index("class TakeObservable<T>")
        end = src.index("\nend", start)
        body = src[start:end]
        self.assertIn("if count < 0; then", body)
        self.assertIn('Err("take count must be nonnegative")', body)
        tests = ROOT / "tests"
        self.assertTrue((tests / "negative_take.ores").is_file())
        self.assertIn("take count must be nonnegative",
                      (tests / "negative_take.err").read_text())

    def test_positive_and_negative_fixtures_are_wired(self):
        tests = ROOT / "tests"
        self.assertEqual((tests / "skip_composition.out").read_text().strip(),
                         EXPECTED[KIND])
        self.assertIn("skip count must be nonnegative",
                      (tests / "negative_skip.err").read_text())
        self.assertTrue((tests / "negative_skip.ores").is_file())
        self.assertTrue((tests / "skip.ores").is_file())
        self.assertIn(".err", (ROOT / "scripts/test.py").read_text())

    def test_callback_variant_never_uses_suspending_language_calls(self):
        if KIND != "callbacks":
            self.skipTest("callback-only invariant")
        source = (ROOT / "src/rx.ores").read_text()
        code = "\n".join(line.split("//")[0] for line in source.splitlines())
        self.assertNotRegex(code, r"\b(?:await|readch|writech|select)\b")
        self.assertNotRegex(code, r"\b(?:Future|Channel)\s*<")

    def test_future_variant_cleans_up_once(self):
        if KIND != "pull":
            self.skipTest("pull/Future-specific invariant")
        source = (ROOT / "src/rx.ores").read_text()
        self.assertIn("dispose_once(mut self)()", source)
        self.assertIn("self.disposed = true;", source)
        self.assertRegex(source, r"pub fnc first<T>\([\s\S]*?finally \{\s*sub.cancel\(\);")

if __name__ == "__main__":
    unittest.main()
