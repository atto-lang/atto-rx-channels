"""Admit a nonempty fixture set with one explicit expectation per program."""
from pathlib import Path


def validate_cases(directory, suffixes):
    directory = Path(directory)
    cases = sorted(directory.glob('*.ores'))
    if not cases:
        raise RuntimeError(f'test inventory must not be empty: {directory}')
    for case in cases:
        if not case.is_file():
            raise RuntimeError(f'test case must be a file: {case}')
        expected = [case.with_suffix(suffix) for suffix in suffixes if case.with_suffix(suffix).is_file()]
        if len(expected) != 1:
            raise RuntimeError(f'exactly one expected result is required: {case}')
        if expected[0].suffix == '.err' and not expected[0].read_text().strip():
            raise RuntimeError(f'negative expectation must not be empty: {expected[0]}')
    admitted = {case.name for case in cases}
    seen = set()
    for suffix in sorted(suffixes, key=len, reverse=True):
        for expected in directory.glob('*' + suffix):
            if expected in seen:
                continue
            seen.add(expected)
            if expected.name[:-len(suffix)] + '.ores' not in admitted:
                raise RuntimeError(f'orphan expected result: {expected}')
    return cases
