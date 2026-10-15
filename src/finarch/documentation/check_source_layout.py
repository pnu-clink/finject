"""Run offline regressions and record failures for before/after comparison."""
import argparse
import json
from pathlib import Path
import socket
import subprocess
import sys
import unittest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('directories', nargs='+')
    args = parser.parse_args()
    sys.path.insert(0, str(args.root / 'src'))
    original_connect = socket.socket.connect
    original_popen = subprocess.Popen

    def local_connect(connection, address):
        if isinstance(address, tuple) and address[0] not in ('127.0.0.1', 'localhost', '::1'):
            raise AssertionError('OFFLINE_CHECK_BLOCKED_NETWORK')
        return original_connect(connection, address)

    def local_process(command, *positional, **keywords):
        executable = command[0] if isinstance(command, (list, tuple)) else command.split()[0]
        if Path(executable).name in ('codex', 'claude', 'gemini', 'ssh', 'curl'):
            raise AssertionError('OFFLINE_CHECK_BLOCKED_MODEL_OR_REMOTE_PROCESS')
        return original_popen(command, *positional, **keywords)

    socket.socket.connect = local_connect
    subprocess.Popen = local_process
    totals = {'tests': 0, 'failures': {}, 'errors': {}, 'skipped': [], 'new_model_calls': 0}
    for directory in args.directories:
        suite = unittest.TestLoader().discover(str(args.root / directory))
        result = unittest.TextTestRunner(verbosity=1).run(suite)
        totals['tests'] += result.testsRun
        for field in ('errors', 'failures'):
            totals[field].update({test.id(): error for test, error in getattr(result, field)})
        totals['skipped'].extend((test.id(), why) for test, why in result.skipped)
    args.output.write_text(json.dumps(totals, indent=2) + '\n')
    print(json.dumps({k: len(v) if isinstance(v, (dict, list)) else v for k, v in totals.items()}))


if __name__ == '__main__':
    main()
