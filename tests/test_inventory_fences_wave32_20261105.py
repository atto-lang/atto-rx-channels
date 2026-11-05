"""Source-owned host fixture inventory checks, not guest channel execution."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / "scripts/fixture_inventory.py"
SPEC = importlib.util.spec_from_file_location("rx_inventory_wave32", MODULE)
inventory = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inventory)
SUFFIXES = (".out", ".err", ".check.err")


class FixtureInventoryFences(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def write(self, name, content):
        (self.root / name).write_text(content)

    def validate(self):
        return inventory.validate_cases(self.root, SUFFIXES)

    def test_deterministic_success_order_and_exact_positive_expectations(self):
        self.write("zeta.ores", "fixture")
        self.write("zeta.out", "zeta\n")
        self.write("alpha.ores", "fixture")
        self.write("alpha.out", "alpha\n")
        self.assertEqual([p.name for p in self.validate()],
                         ["alpha.ores", "zeta.ores"])

    def test_multiple_competing_oracles_do_not_authenticate_guest_behavior(self):
        self.write("subject.ores", "fixture")
        self.write("subject.out", "pass\n")
        self.write("subject.check.err", "expected denial\n")
        with self.assertRaisesRegex(RuntimeError, "exactly one expected result"):
            self.validate()

    def test_blank_negative_expectation_cannot_accept_arbitrary_error(self):
        self.write("subject.ores", "fixture")
        self.write("subject.check.err", " \n\t ")
        with self.assertRaisesRegex(RuntimeError, "negative expectation must not be empty"):
            self.validate()

    def test_orphan_expected_files_and_empty_inventory_are_denied(self):
        with self.assertRaisesRegex(RuntimeError, "inventory must not be empty"):
            self.validate()
        self.write("live.ores", "fixture")
        self.write("live.out", "value\n")
        self.write("orphan.check.err", "unrelated denial")
        with self.assertRaisesRegex(RuntimeError, "orphan expected result"):
            self.validate()

    def test_one_nonempty_negative_oracle_is_admitted_as_shape_only(self):
        self.write("denied.ores", "fixture")
        self.write("denied.err", "specific compiler diagnostic\n")
        self.assertEqual([p.name for p in self.validate()], ["denied.ores"])


if __name__ == "__main__":
    unittest.main()
