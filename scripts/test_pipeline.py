#!/usr/bin/env python3
"""Build the pinned Java compiler and execute the real AttoLang pipeline.

This is a process/output harness. No application behavior is modeled in Python.
Receipts include every command, status, stdout and stderr, even on failure.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--compiler', required=True, type=Path)
parser.add_argument('--output', required=True, type=Path)
parser.add_argument('--repeat', type=int, default=20)
args = parser.parse_args()
if not 1 <= args.repeat <= 100:
    parser.error('--repeat must be between 1 and 100')
compiler = args.compiler.resolve(strict=True)
output = args.output.resolve()
output.mkdir(parents=True, exist_ok=True)
pin = json.loads((ROOT / 'pipeline-compiler.lock').read_text())
receipt = {'pin': pin, 'commands': [], 'status': 'FAIL', 'repeat': args.repeat}


def execute(command, cwd=ROOT, timeout=120):
    command = [str(item) for item in command]
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout)
    receipt['commands'].append(dict(command=command, cwd=str(cwd), exit_status=result.returncode,
                                    stdout=result.stdout, stderr=result.stderr))
    return result


def succeed(command, cwd=ROOT, timeout=120):
    result = execute(command, cwd, timeout)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return result.stdout.strip()


try:
    for key, spec in [('commit', 'HEAD'), ('tree', 'HEAD^{tree}')]:
        actual = succeed(['git', 'rev-parse', spec], compiler)
        if actual != pin[key]:
            raise RuntimeError(f'compiler {key}: expected {pin[key]}, got {actual}')
    if succeed(['git', 'status', '--porcelain', '--untracked-files=all'], compiler):
        raise RuntimeError('compiler checkout must be clean, including test overlays')
    receipt['application_commit'] = succeed(['git', 'rev-parse', 'HEAD'])
    receipt['application_tree'] = succeed(['git', 'rev-parse', 'HEAD^{tree}'])
    if succeed(['git', 'status', '--porcelain', '--untracked-files=all']):
        raise RuntimeError('commit application changes before recording exact-source evidence')
    java_home = Path(os.environ['JAVA_HOME'])
    java = java_home / 'bin/java'
    javac = java_home / 'bin/javac'
    version = execute([java, '-version'])
    if version.returncode or 'version "25.' not in version.stderr:
        raise RuntimeError('JAVA_HOME must name JDK 25')
    succeed(['mvn', '-q', '-DskipTests', 'clean', 'package'], compiler, 300)
    succeed(['mvn', '-q', 'dependency:build-classpath', '-Dmdep.outputFile=target/cp.txt'], compiler)
    classpath = str(compiler / 'target/classes') + os.pathsep + (compiler / 'target/cp.txt').read_text().strip()
    command = [java, '--enable-native-access=ALL-UNNAMED',
               '-Dpolyglot.engine.WarnInterpreterOnly=false', '-cp', classpath,
               'dev.oreslang.launcher.OresMain']
    cases = [ROOT / 'examples/worker_pipeline.atto', *sorted((ROOT / 'tests/pipeline').glob('*.atto'))]
    positives = []
    receipt['source_sha256'] = {}
    for path in [ROOT / 'src/worker_pipeline.atto', *cases]:
        if path.is_symlink() or not path.is_file():
            raise RuntimeError(f'not a regular guest source: {path}')
        receipt['source_sha256'][str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
        negative = path.with_suffix('.check.err')
        oracle = negative if negative.exists() else path.with_suffix('.out')
        if path.name != 'worker_pipeline.atto' or path.parent.name != 'src':
            if oracle.is_symlink() or not oracle.is_file():
                raise RuntimeError(f'missing regular oracle: {oracle}')
        result = execute([*command, '--check', path])
        if negative.exists():
            expected = negative.read_text().strip()
            if not expected or not result.returncode or expected not in result.stderr:
                raise RuntimeError(f'expected compiler rejection: {path}\n{result.stderr}')
            print(f'PASS {path.name} (expected actor-boundary rejection)', flush=True)
        else:
            if result.returncode or ': error:' in result.stderr:
                raise RuntimeError(f'check failed: {path}\n{result.stderr}')
            if path in cases:
                positives.append(path)
    probe_classes = output / 'classes'
    probe_classes.mkdir(exist_ok=True)
    succeed([javac, '-cp', classpath, '-d', probe_classes, ROOT / 'tools/ChannelPipelineGuestProbe.java'])
    probe = [java, '--enable-native-access=ALL-UNNAMED',
             '-Dpolyglot.engine.WarnInterpreterOnly=false', '-cp', str(probe_classes) + os.pathsep + classpath,
             'dev.oreslang.launcher.ChannelPipelineGuestProbe']
    result = succeed([*probe, *(positives * args.repeat)], timeout=120)
    print(result, flush=True)
    receipt['positive_executions'] = len(positives) * args.repeat
    receipt['expected_outputs'] = {str(path.relative_to(ROOT)): path.with_suffix('.out').read_text().strip()
                                   for path in positives}
    receipt['status'] = 'PASS'
finally:
    (output / 'pipeline-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
