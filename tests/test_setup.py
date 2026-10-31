"""Real Git preflight regressions; Maven is a fixture, not a compiler proof."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class CompilerSetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'project with spaces'
        (self.root / 'scripts').mkdir(parents=True)
        shutil.copyfile(ROOT / 'scripts/setup.py', self.root / 'scripts/setup.py')
        self.source = self.root / '.work/oreslang-source.java'
        self.source.mkdir(parents=True)
        self.git('init', '-q')
        self.git('config', 'user.email', 'test@example.invalid')
        self.git('config', 'user.name', 'Setup test')
        (self.source / 'pom.xml').write_text('<project/>')
        self.git('add', 'pom.xml')
        self.git('commit', '-qm', 'fixture')
        self.sha = self.git('rev-parse', 'HEAD').strip()
        (self.root / 'compiler.lock').write_text(self.sha + '\n')
        if (ROOT / 'compiler-tree.txt').exists():
            (self.root / 'compiler-tree.txt').write_text(self.git('rev-parse', 'HEAD^{tree}'))
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.log = self.root / 'maven.jsonl'
        fake = self.bin / 'mvn'
        fake.write_text('#!' + sys.executable + '\nimport json,os,pathlib,sys\n'
            'with open(os.environ["MVN_LOG"],"a") as f: f.write(json.dumps(sys.argv[1:])+"\\n")\n'
            'if os.environ.get("FAIL_MVN"): sys.exit(19)\n'
            'for arg in sys.argv[1:]:\n'
            ' if arg.startswith("-Dmdep.outputFile="):\n'
            '  path=pathlib.Path(arg.split("=",1)[1])\n'
            '  if os.environ.get("POISON_CLASSPATH"): path.symlink_to(os.environ["POISON_CLASSPATH"])\n'
            '  else: path.write_text("fixture-dependency.jar")\n')
        fake.chmod(0o700)
        self.env = dict(os.environ, PATH=str(self.bin)+os.pathsep+os.environ['PATH'], MVN_LOG=str(self.log))
    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.source), *args], text=True)
    def run_setup(self):
        return subprocess.run([sys.executable, str(self.root / 'scripts/setup.py')],
                              env=self.env, capture_output=True, text=True, timeout=10)
    def test_clean_pin_skips_network_and_cleans_build_outputs(self):
        result = self.run_setup()
        self.assertEqual(result.returncode, 0, result.stderr)
        commands = [json.loads(x) for x in self.log.read_text().splitlines()]
        self.assertIn('clean', commands[0])
        self.assertTrue((self.root / '.work/env.sh').read_text().startswith('export ORES_CLASSPATH='))
    def test_first_install_builds_the_exact_pin(self):
        remote = self.source.with_name('fixture-origin')
        self.source.rename(remote)
        script = self.root / 'scripts/setup.py'
        script.write_text(script.read_text().replace(
            'https://github.com/ores-truffle-oreslang/oreslang-source.java.git', str(remote)))
        result = self.run_setup()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git('rev-parse', 'HEAD').strip(), self.sha)
    def test_floating_pin_refused_before_build(self):
        (self.root / 'compiler.lock').write_text('main')
        result = self.run_setup()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('full Git SHAs', result.stderr)
        self.assertFalse(self.log.exists())
    def test_dirty_source_preserved_without_fetch_or_build(self):
        (self.source / 'pom.xml').write_text('local work')
        result = self.run_setup()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('must be clean', result.stderr)
        self.assertEqual((self.source / 'pom.xml').read_text(), 'local work')
        self.assertEqual(self.git('rev-parse', 'HEAD').strip(), self.sha)
        self.assertFalse(self.log.exists())
    def test_untracked_source_refused(self):
        (self.source / 'Untracked.java').write_text('local source')
        self.assertNotEqual(self.run_setup().returncode, 0)
        self.assertFalse(self.log.exists())
    def test_failed_build_removes_stale_launcher(self):
        launcher = self.root / '.work/env.sh'
        launcher.write_text('old compiler')
        self.env['FAIL_MVN'] = '1'
        self.assertNotEqual(self.run_setup().returncode, 0)
        self.assertFalse(launcher.exists())
    def test_symlinked_source_refused(self):
        moved = self.source.with_name('other-compiler')
        self.source.rename(moved)
        self.source.symlink_to(moved, target_is_directory=True)
        result = self.run_setup()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('must not be a symlink', result.stderr)
        self.assertFalse(self.log.exists())


    def test_symlinked_work_root_refused_before_clone_or_build(self):
        work = self.root / '.work'
        actual = self.root / 'moved-work'
        work.rename(actual)
        work.symlink_to(actual, target_is_directory=True)
        result = self.run_setup()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('work directory must be a real directory', result.stderr)
        self.assertFalse(self.log.exists())

    def test_symlinked_classpath_refused_before_build(self):
        outside = self.root / 'outside.txt'
        outside.write_text('must remain unchanged')
        (self.root / '.work/classpath.txt').symlink_to(outside)
        result = self.run_setup()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('classpath must be a regular file', result.stderr)
        self.assertEqual(outside.read_text(), 'must remain unchanged')
        self.assertFalse(self.log.exists())

    def test_classpath_directory_masquerade_refused_before_build(self):
        (self.root / '.work/classpath.txt').mkdir()
        result = self.run_setup()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('classpath must be a regular file', result.stderr)
        self.assertFalse(self.log.exists())


    def test_post_build_classpath_symlink_refused_before_publish(self):
        outside = self.root / 'outside-classpath.txt'
        outside.write_text('trusted sentinel')
        self.env['POISON_CLASSPATH'] = str(outside)
        result = self.run_setup()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('classpath must be a regular file after build', result.stderr)
        self.assertEqual(outside.read_text(), 'trusted sentinel')
        self.assertFalse((self.root / '.work/env.sh').exists())

    def test_preexisting_launcher_symlink_not_followed(self):
        outside = self.root / 'outside-launcher.txt'
        outside.write_text('trusted sentinel')
        launcher = self.root / '.work/env.sh'
        launcher.symlink_to(outside)
        result = self.run_setup()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(outside.read_text(), 'trusted sentinel')
        self.assertFalse(launcher.is_symlink())
        self.assertTrue(launcher.read_text().startswith('export ORES_CLASSPATH='))

    def test_launcher_temporary_name_uses_exclusive_random_creation(self):
        setup = (self.root / 'scripts/setup.py').read_text()
        self.assertIn('tempfile.NamedTemporaryFile(', setup)
        self.assertIn('delete=False', setup)
        self.assertNotIn('os.getpid()', setup)

if __name__ == '__main__': unittest.main()
