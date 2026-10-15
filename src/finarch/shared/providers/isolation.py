"""macOS process file boundaries, independent of model tool instructions."""
import json
import sys
from pathlib import Path

ROOT = (Path(__file__).resolve().parent / '../../../..').resolve()
PYTHON_BINARY = Path(sys.base_prefix)/'Resources/Python.app/Contents/MacOS/Python'
if not PYTHON_BINARY.exists():
    PYTHON_BINARY = Path(sys._base_executable).resolve()


def cli_profile():
    protected = [ROOT, ROOT.parent/'fin-astra']
    deny = ' '.join('(subpath '+json.dumps(str(p),ensure_ascii=False)+')' for p in protected)
    policy = Path(__file__).with_name('policy.py')
    return '(version 1)\n(allow default)\n(deny file-read* '+deny+')\n(deny file-write* '+deny+')\n(allow file-read* (literal '+json.dumps(str(policy),ensure_ascii=False)+'))\n'


def python_profile(input_path, worker, stdout_path, stderr_path):
    runtime = [Path(sys.base_prefix).resolve(), Path('/System'), Path('/usr/lib'), Path('/Library/Apple'), Path('/dev')]
    readable = ' '.join('(subpath '+json.dumps(str(p),ensure_ascii=False)+')' for p in runtime)
    files = ' '.join('(literal '+json.dumps(str(Path(p).resolve()),ensure_ascii=False)+')' for p in (input_path,worker,PYTHON_BINARY))
    writable = ' '.join('(literal '+json.dumps(str(Path(p).resolve()),ensure_ascii=False)+')' for p in (stdout_path,stderr_path))
    return ('(version 1)\n(allow default)\n(deny network*)\n(deny process-fork)\n'
            '(deny process-exec)\n(allow process-exec (literal '+json.dumps(str(PYTHON_BINARY.resolve()),ensure_ascii=False)+'))\n'
            '(deny file-read*)\n(allow file-read-metadata)\n(allow file-read* (literal "/") '+readable+' '+files+')\n'
            '(deny file-write*)\n(allow file-write* '+writable+')\n')
