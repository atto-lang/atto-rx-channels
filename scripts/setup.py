#!/usr/bin/env python3
"""Build the pinned compiler without carrying local edits or stale classes."""
from pathlib import Path
import os
import re
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / '.work' / 'oreslang-source.java'
REVISION = (ROOT / 'compiler.lock').read_text().strip()
TREE_FILE = ROOT / 'compiler-tree.txt'
EXPECTED_TREE = TREE_FILE.read_text().strip() if TREE_FILE.exists() else None
if not re.fullmatch(r'[0-9a-f]{40}', REVISION) or (EXPECTED_TREE is not None and
        not re.fullmatch(r'[0-9a-f]{40}', EXPECTED_TREE)):
    raise SystemExit('compiler revision and tree must be full Git SHAs')
if SOURCE.is_symlink():
    raise SystemExit('compiler path must not be a symlink')
SOURCE.parent.mkdir(exist_ok=True)
if not SOURCE.exists():
    subprocess.run(['git', 'clone', '--depth', '1',
                    'https://github.com/ores-truffle-oreslang/oreslang-source.java.git',
                    str(SOURCE)], check=True)

def git(*args):
    return subprocess.check_output(['git', '-C', str(SOURCE), *args], text=True).strip()

if Path(git('rev-parse', '--show-toplevel')).resolve() != SOURCE.resolve():
    raise SystemExit('compiler path must be its own Git checkout')
# Refuse before fetch/checkout can change HEAD or preserve edits on a new pin.
if git('status', '--porcelain', '--untracked-files=all'):
    raise SystemExit('compiler checkout must be clean; preserve local changes before building')
head = subprocess.run(['git', '-C', str(SOURCE), 'rev-parse', '--verify', 'HEAD'],
                      text=True, capture_output=True)
matched = head.returncode == 0 and head.stdout.strip() == REVISION
# A same-repository mirror may have a different commit but the exact pinned tree.
if EXPECTED_TREE is not None and head.returncode == 0:
    matched = git('rev-parse', 'HEAD^{tree}') == EXPECTED_TREE
if not matched:
    subprocess.run(['git', '-C', str(SOURCE), 'fetch', '--depth', '1', 'origin', REVISION], check=True)
    subprocess.run(['git', '-C', str(SOURCE), 'checkout', '--detach', REVISION], check=True)
if EXPECTED_TREE is not None and git('rev-parse', 'HEAD^{tree}') != EXPECTED_TREE:
    raise SystemExit('compiler source tree does not match compiler-tree.txt')
if EXPECTED_TREE is None and git('rev-parse', 'HEAD') != REVISION:
    raise SystemExit('compiler revision does not match compiler.lock')
if git('status', '--porcelain', '--untracked-files=all'):
    raise SystemExit('compiler checkout must be clean before building')
# Remove a previous launcher before building: a failed setup must not publish
# an old classpath as the newly requested compiler. clean removes stale classes.
environment = ROOT / '.work' / 'env.sh'
environment.unlink(missing_ok=True)
subprocess.run(['mvn', '-q', '-f', str(SOURCE / 'pom.xml'), '-DskipTests', 'clean', 'package'], check=True)
classpath_file = ROOT / '.work' / 'classpath.txt'
subprocess.run(['mvn', '-q', '-f', str(SOURCE / 'pom.xml'), 'dependency:build-classpath',
                f'-Dmdep.outputFile={classpath_file}'], check=True)
classpath = str(SOURCE / 'target/classes') + os.pathsep + classpath_file.read_text().strip()
temporary = environment.with_name('env.sh.' + str(os.getpid()) + '.tmp')
try:
    temporary.write_text('export ORES_CLASSPATH=' + shlex.quote(classpath) + '\n')
    temporary.replace(environment)
finally:
    temporary.unlink(missing_ok=True)
print('Compiler ready. Run: source .work/env.sh && python3 scripts/test.py')
