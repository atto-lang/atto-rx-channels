"""Admit only in-tree regular Oreslang fixtures and exactly one expectation."""
from pathlib import Path


def validate_cases(directory, suffixes):
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise RuntimeError(f'test directory must be a real directory: {directory}')
    root = directory.resolve(strict=True)

    def require_regular(path):
        # A symlink can expose local files to the compiler, the runner, or logs;
        # also reject dangling symlinks and directories pretending to be files.
        if path.is_symlink() or not path.is_file() or path.resolve(strict=True).parent != root:
            raise RuntimeError(f'fixture must be an in-tree regular file: {path}')

    cases = sorted(directory.glob('*.ores'))
    if not cases:
        raise RuntimeError(f'test inventory must not be empty: {directory}')
    for case in cases:
        require_regular(case)
        expectations = [case.with_suffix(suffix) for suffix in suffixes
                        if case.with_suffix(suffix).exists() or case.with_suffix(suffix).is_symlink()]
        if len(expectations) != 1:
            raise RuntimeError(f'exactly one expected result is required: {case}')
        require_regular(expectations[0])
        if expectations[0].name.endswith('.err') and not expectations[0].read_text().strip():
            raise RuntimeError(f'negative expectation must not be empty: {expectations[0]}')
    admitted = {case.name for case in cases}
    seen = set()
    for suffix in sorted(suffixes, key=len, reverse=True):
        for expected in directory.glob('*' + suffix):
            if expected in seen:
                continue
            seen.add(expected)
            require_regular(expected)
            if expected.name[:-len(suffix)] + '.ores' not in admitted:
                raise RuntimeError(f'orphan expected result: {expected}')
    return cases
