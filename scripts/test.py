#!/usr/bin/env python3
"""Check and run real .ores programs, with bounded execution and exact output."""
import os
import re
from pathlib import Path
import subprocess
import sys
from fixture_inventory import validate_cases

ROOT = Path(__file__).resolve().parents[1]
JAVA = os.environ.get('JAVA', 'java')
CLASSPATH = os.environ.get('ORES_CLASSPATH')
if not CLASSPATH:
    sys.exit('Set ORES_CLASSPATH to the reference compiler classes and dependencies (see README).')
COMMAND = [JAVA, '--enable-native-access=ALL-UNNAMED',
           '-Dpolyglot.engine.WarnInterpreterOnly=false', '-cp', CLASSPATH,
           'dev.oreslang.launcher.OresMain']

POINTER_STYLE = (
    (re.compile(r'Fnc\s*<\s*&'), 'borrow marker inside Fnc<...>'),
    (re.compile(r'&mut\b'), 'pointer-style &mut'),
    (re.compile(r'(^|[\(\[,=])\s*&\s*[A-Za-z_(]', re.MULTILINE),
     'unary address-of style &value'),
    (re.compile(r'\b(?:[A-Z][A-Za-z0-9_]*(?:<[^>\n]+>)?|int|bool|string|String)\s*\*\s+[A-Za-z_]'),
     'pointer-style T* declaration'),
)

def assert_pointerless():
    for directory in ('src', 'tests', 'bench', 'examples'):
        root = ROOT / directory
        for path in checked_sources(root):
            text = path.read_text()
            for pattern, label in POINTER_STYLE:
                match = pattern.search(text)
                if match:
                    line = text.count('\n', 0, match.start()) + 1
                    sys.exit(f'{path}:{line}: forbidden {label}; use pointerless rt ownership semantics')

def checked_sources(root):
    # Validate all executable and regex-scanned .ores paths before opening them.
    # Purely source-local preflight; this does not make a writable tree TOCTOU-safe.
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        sys.exit(f'source directory must be a real directory: {root}')
    parent = root.resolve(strict=True) if root.exists() else None
    for path in sorted(root.glob('*.ores')):
        if (path.is_symlink() or not path.is_file() or
                path.resolve(strict=True).parent != parent):
            sys.exit(f'source must be an in-tree regular file: {path}')
        yield path

def run(args):
    result = subprocess.run(COMMAND + args, text=True, capture_output=True, timeout=30)
    if result.returncode or ': error:' in result.stderr:
        raise RuntimeError(result.stdout + result.stderr)
    return result.stdout.strip()

TESTS = validate_cases(ROOT / 'tests', ('.out', '.err', '.check.err'))
assert_pointerless()
for source in checked_sources(ROOT / 'src'):
    run(['--check', str(source)])
for example in checked_sources(ROOT / 'examples'):
    run(['--check', str(example)])
failures = []
for path in TESTS:
    try:
        check_error_file = path.with_suffix('.check.err')
        if check_error_file.exists():
            result = subprocess.run(COMMAND + ['--check', str(path)], text=True, capture_output=True, timeout=30)
            expected_check_error = check_error_file.read_text().strip()
            if result.returncode == 0 or expected_check_error not in result.stderr:
                raise RuntimeError(f'expected check failure containing {expected_check_error!r}\n'
                                   + result.stdout + result.stderr)
            print(f'PASS {path.stem} (expected check failure)', flush=True)
            continue

        run(['--check', str(path)])
        error_file = path.with_suffix('.err')
        if error_file.exists():
            result = subprocess.run(COMMAND + [str(path)], text=True, capture_output=True, timeout=30)
            expected_error = error_file.read_text().strip()
            if result.returncode == 0 or expected_error not in result.stderr:
                raise RuntimeError(f'expected failure containing {expected_error!r}\n'
                                   + result.stdout + result.stderr)
            print(f'PASS {path.stem} (expected failure)', flush=True)
            continue
        actual = run([str(path)])
        expected = path.with_suffix('.out').read_text().strip()
        if actual != expected:
            raise RuntimeError(f'expected {expected!r}, got {actual!r}')
        print(f'PASS {path.stem}', flush=True)
    except (RuntimeError, subprocess.TimeoutExpired, OSError) as error:
        failures.append(path.stem)
        print(f'FAIL {path.stem}: {error}', file=sys.stderr, flush=True)

if failures:
    sys.exit(f'{len(failures)} failing Rx programs: {", ".join(failures)}')
print('All Rx programs passed.')
