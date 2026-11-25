"""Adversarial source-identity admission tests; no private source/guest execution."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_ci_source_head_20261106.sh"


class ExactHeadAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "source"
        self.root.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "user.name", "Identity Fixture")
        (self.root / ".gitignore").write_text("*.shadow\n", encoding="utf-8")
        (self.root / "program.atto").write_text("pub fnc main(): int { return 42; }\n", encoding="utf-8")
        self.git("add", ".gitignore", "program.atto")
        self.git("commit", "-qm", "fixture")
        self.head = self.git("rev-parse", "HEAD").stdout.strip()

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], capture_output=True,
                              text=True, check=True)

    def check(self, expected=None, cwd=None, extra_env=None):
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env["EXPECTED_HEAD"] = self.head if expected is None else expected
        env.update(extra_env or {})
        return subprocess.run(["bash", str(SCRIPT)], cwd=cwd or self.root,
                              env=env, capture_output=True, text=True)

    def test_exact_head_pristine_tree_is_admitted(self):
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"commit={self.head}", result.stdout)
        self.assertIn("tree=", result.stdout)

    def test_missing_or_noncanonical_sha_is_denied(self):
        for bad in ["", "0" * 39, "A" * 40, "z" * 40, "0" * 40 + "\n", "  " + self.head]:
            with self.subTest(bad=repr(bad)):
                self.assertEqual(self.check(expected=bad).returncode, 65)

    def test_mismatched_commit_is_denied(self):
        result = self.check(expected="0" * 40)
        self.assertEqual(result.returncode, 65)
        self.assertIn("original event commit", result.stderr)

    def test_same_tree_different_commit_is_denied(self):
        self.git("commit", "--allow-empty", "-qm", "new history, same tree")
        self.assertNotEqual(self.git("rev-parse", "HEAD").stdout.strip(), self.head)
        self.assertEqual(self.check().returncode, 65)

    def test_subdirectory_cannot_impersonate_checkout_root(self):
        sub = self.root / "subdir"
        sub.mkdir()
        self.assertEqual(self.check(cwd=sub).returncode, 65)

    def test_staged_source_change_is_denied(self):
        (self.root / "program.atto").write_text("pub fnc main(): int { return 1; }\n")
        self.git("add", "program.atto")
        self.assertEqual(self.check().returncode, 65)

    def test_unstaged_source_change_is_denied(self):
        (self.root / "program.atto").write_text("pub fnc main(): int { return 1; }\n")
        self.assertEqual(self.check().returncode, 65)

    def test_untracked_source_change_is_denied(self):
        (self.root / "unexpected.atto").write_text("bad")
        self.assertEqual(self.check().returncode, 65)

    def test_ignored_shadow_is_denied(self):
        (self.root / "compiler.shadow").write_text("bad")
        self.assertEqual(self.check().returncode, 65)

    def test_inherited_git_dir_is_denied(self):
        result = self.check(extra_env={"GIT_DIR": str(self.root / ".git")})
        self.assertEqual(result.returncode, 65)
        self.assertIn("Git control environment", result.stderr)

    def test_inherited_git_config_is_denied(self):
        self.assertEqual(self.check(extra_env={"GIT_CONFIG_COUNT": "0"}).returncode, 65)


if __name__ == "__main__":
    unittest.main()
