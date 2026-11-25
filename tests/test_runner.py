"""Black-box host runner contracts; Java is a fixture, not compiler evidence."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

CALLBACK = False
CHANNELS = True


class RunnerInventory(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'scripts').mkdir()
        source = Path(__file__).resolve().parents[1]/'scripts'
        for name in ('test.py','fixture_inventory.py'):
            shutil.copy(source/name,self.root/'scripts'/name)
        (self.root/'src').mkdir()
        (self.root/'src/rx.ores').write_text('fixture')
        (self.root/'tests').mkdir()
        self.marker = self.root/'java-called'
        java = self.root/'java'
        java.write_text('#!'+sys.executable+'\nimport sys\nfrom pathlib import Path\n'
            'Path('+repr(str(self.marker))+').touch()\n'
            'if "--check" in sys.argv:\n'
            ' if "reject" in sys.argv[-1]:\n'
            '  print("expected rejection",file=sys.stderr);sys.exit(1)\n'
            'else:\n print("hello")\n')
        java.chmod(0o755)
        self.env = {**os.environ,'JAVA':str(java),'ORES_CLASSPATH':'host-fixture-only'}

    def seed(self):
        (self.root/'tests/case.ores').write_text('fixture')
        (self.root/'tests/case.out').write_text('hello\n')
        if CALLBACK:
            (self.root/'tests/reject').mkdir()
            (self.root/'tests/reject/case.ores').write_text('fixture')
            (self.root/'tests/reject/case.err').write_text('expected rejection')

    def run_script(self):
        return subprocess.run([sys.executable,'scripts/test.py'],cwd=self.root,env=self.env,
                              capture_output=True,text=True,timeout=5)

    def rejected(self,message):
        result=self.run_script()
        self.assertNotEqual(result.returncode,0,result.stdout)
        self.assertIn(message,result.stderr)
        self.assertFalse(self.marker.exists(),'invalid inventory must fail before Java invocation')

    def test_valid_control_invokes_runner(self):
        self.seed()
        result=self.run_script()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('PASS case',result.stdout)
        self.assertTrue(self.marker.exists())

    def test_empty_suite_rejected_before_compiler(self):
        self.rejected('inventory must not be empty')

    def test_missing_expectation_rejected_before_compiler(self):
        self.seed()
        (self.root/'tests/case.out').unlink()
        self.rejected('exactly one expected result')

    def test_orphan_expectation_rejected_before_compiler(self):
        self.seed()
        (self.root/'tests/orphan.out').write_text('obsolete')
        self.rejected('orphan expected result')

    def test_empty_negative_cannot_match_any_failure(self):
        if not (CALLBACK or CHANNELS):
            self.skipTest('runner supports output-only expectations')
        self.seed()
        if CALLBACK:
            path=self.root/'tests/reject/case.err'
        else:
            (self.root/'tests/case.out').unlink()
            path=self.root/'tests/case.check.err'
        path.write_text(' \n')
        self.rejected('negative expectation must not be empty')


    def test_symlinked_source_rejected_before_compiler(self):
        self.seed()
        outside = self.root/'untrusted.ores'
        outside.write_text('untrusted source')
        case = self.root/'tests/case.ores'
        case.unlink()
        case.symlink_to(outside)
        self.rejected('in-tree regular file')

    def test_symlinked_expectation_rejected_before_compiler(self):
        self.seed()
        outside = self.root/'untrusted.out'
        outside.write_text('hello\\n')
        expected = self.root/'tests/case.out'
        expected.unlink()
        expected.symlink_to(outside)
        self.rejected('in-tree regular file')

    def test_dangling_expectation_rejected_before_compiler(self):
        self.seed()
        expected = self.root/'tests/case.out'
        expected.unlink()
        expected.symlink_to(self.root/'missing.out')
        self.rejected('in-tree regular file')

    def test_expected_directory_rejected_before_compiler(self):
        self.seed()
        expected = self.root/'tests/case.out'
        expected.unlink()
        expected.mkdir()
        self.rejected('in-tree regular file')

    def test_symlinked_suite_root_rejected_before_compiler(self):
        self.seed()
        original = self.root/'tests'
        actual = self.root/'actual-tests'
        original.rename(actual)
        original.symlink_to(actual, target_is_directory=True)
        self.rejected('test directory must be a real directory')

    def test_symlinked_callback_rejection_rejected_before_compiler(self):
        if not CALLBACK:
            self.skipTest('separate reject suite is callback-only')
        self.seed()
        outside = self.root/'untrusted.err'
        outside.write_text('expected rejection')
        expected = self.root/'tests/reject/case.err'
        expected.unlink()
        expected.symlink_to(outside)
        self.rejected('in-tree regular file')


    def test_symlinked_library_source_rejected_before_compiler(self):
        self.seed()
        outside = self.root / 'outside.ores'
        outside.write_text('not a trusted source')
        library = self.root / 'src/rx.ores'
        library.unlink()
        library.symlink_to(outside)
        self.rejected('source must be an in-tree regular file')

    def test_symlinked_benchmark_source_rejected_before_compiler(self):
        self.seed()
        outside = self.root / 'outside.ores'
        outside.write_text('not a trusted benchmark')
        bench = self.root / 'bench'
        bench.mkdir()
        (bench / 'sample.ores').symlink_to(outside)
        self.rejected('source must be an in-tree regular file')

    def test_symlinked_source_directory_rejected_before_compiler(self):
        self.seed()
        src = self.root / 'src'
        moved = self.root / 'moved-src'
        src.rename(moved)
        src.symlink_to(moved, target_is_directory=True)
        self.rejected('source directory must be a real directory')

    def test_benchmark_directory_masquerade_rejected_before_compiler(self):
        self.seed()
        (self.root / 'bench').write_text('not a directory')
        self.rejected('source directory must be a real directory')

    def test_symlinked_example_rejected_before_compiler(self):
        if not CHANNELS:
            self.skipTest('only the channels runner checks example sources')
        self.seed()
        outside = self.root / 'outside.ores'
        outside.write_text('untrusted example')
        example_dir = self.root / 'examples'
        example_dir.mkdir()
        (example_dir / 'demo.ores').symlink_to(outside)
        self.rejected('source must be an in-tree regular file')



if __name__=='__main__':
    unittest.main()
