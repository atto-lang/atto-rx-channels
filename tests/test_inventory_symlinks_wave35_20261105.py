"""Host-only symlink alias regressions; no compiled channel execution."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / "scripts/fixture_inventory.py"
SPEC = importlib.util.spec_from_file_location("rx_inventory_wave35", MODULE)
inventory = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inventory)
SUFFIXES = (".out", ".err", ".check.err")


class InventorySymlinkFences(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def case(self):
        (self.root / "case.ores").write_text("fixture\n")
        (self.root / "case.out").write_text("expected\n")

    def check(self):
        return inventory.validate_cases(self.root, SUFFIXES)

    def test_real_source_and_real_oracle_remain_admitted(self):
        self.case()
        self.assertEqual([path.name for path in self.check()], ["case.ores"])

    def test_source_symlink_is_not_an_independent_case_identity(self):
        (self.root / "backing.txt").write_text("fixture\n")
        (self.root / "case.ores").symlink_to("backing.txt")
        (self.root / "case.out").write_text("expected\n")
        with self.assertRaisesRegex(RuntimeError, "test case must be a regular file"):
            self.check()

    def test_oracle_symlink_cannot_import_external_expectations(self):
        (self.root / "case.ores").write_text("fixture\n")
        (self.root / "backing.txt").write_text("expected\n")
        (self.root / "case.out").symlink_to("backing.txt")
        with self.assertRaisesRegex(RuntimeError, "expected result must be a regular file"):
            self.check()

    def test_dangling_oracle_link_is_not_treated_as_missing(self):
        (self.root / "case.ores").write_text("fixture\n")
        (self.root / "case.check.err").symlink_to("missing.txt")
        with self.assertRaisesRegex(RuntimeError, "expected result must be a regular file"):
            self.check()

    def test_orphan_symlink_cannot_borrow_a_valid_case_oracle(self):
        self.case()
        (self.root / "orphan.out").symlink_to("case.out")
        with self.assertRaisesRegex(RuntimeError, "expected result must be a regular file"):
            self.check()


if __name__ == "__main__":
    unittest.main()
