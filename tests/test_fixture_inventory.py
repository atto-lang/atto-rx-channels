"""Source-free regression checks for trusted Oreslang fixture admission."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from fixture_inventory import validate_cases


class FixtureInventoryHardeningTest(unittest.TestCase):
    SUFFIXES = ('.out', '.err', '.check.err')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name) / 'fixtures'
        self.folder.mkdir()
        (self.folder / 'case.ores').write_text('pub fnc main(): void {}\n')
        (self.folder / 'case.out').write_text('ok\n')

    def check(self):
        return validate_cases(self.folder, self.SUFFIXES)

    def test_positive_fixture_admitted(self):
        self.assertEqual([p.name for p in self.check()], ['case.ores'])

    def test_check_error_expectation_admitted(self):
        (self.folder / 'case.out').unlink()
        (self.folder / 'case.check.err').write_text('compiler rejection\n')
        self.check()

    def test_empty_negative_rejected(self):
        (self.folder / 'case.out').unlink()
        (self.folder / 'case.err').write_text(' \n')
        with self.assertRaisesRegex(RuntimeError, 'negative expectation'):
            self.check()

    def test_duplicate_expectations_rejected(self):
        (self.folder / 'case.err').write_text('error\n')
        with self.assertRaisesRegex(RuntimeError, 'exactly one'):
            self.check()

    def test_orphan_expectation_rejected(self):
        (self.folder / 'orphan.out').write_text('wrong\n')
        with self.assertRaisesRegex(RuntimeError, 'orphan'):
            self.check()

    def test_source_symlink_rejected(self):
        external = Path(self.temp.name) / 'external.ores'
        external.write_text('secret content\n')
        (self.folder / 'case.ores').unlink()
        (self.folder / 'case.ores').symlink_to(external)
        with self.assertRaisesRegex(RuntimeError, 'regular file'):
            self.check()

    def test_expected_output_symlink_rejected(self):
        external = Path(self.temp.name) / 'external.txt'
        external.write_text('secret content\n')
        (self.folder / 'case.out').unlink()
        (self.folder / 'case.out').symlink_to(external)
        with self.assertRaisesRegex(RuntimeError, 'regular file'):
            self.check()

    def test_dangling_expected_output_symlink_rejected(self):
        (self.folder / 'case.out').unlink()
        (self.folder / 'case.out').symlink_to(self.folder / 'missing.txt')
        with self.assertRaisesRegex(RuntimeError, 'regular file'):
            self.check()

    def test_directory_disguised_as_fixture_rejected(self):
        (self.folder / 'case.ores').unlink()
        (self.folder / 'case.ores').mkdir()
        with self.assertRaisesRegex(RuntimeError, 'regular file'):
            self.check()

    def test_symlinked_fixture_directory_rejected(self):
        alias = Path(self.temp.name) / 'alias'
        alias.symlink_to(self.folder, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, 'real directory'):
            validate_cases(alias, self.SUFFIXES)


if __name__ == '__main__':
    unittest.main()
