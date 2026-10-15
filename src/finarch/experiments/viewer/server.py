"""Launch the experiment viewer's Node server through the common Python entry."""
import os
from pathlib import Path
import shutil
import sys


def main():
    # Menu bar apps do not inherit the shell's Homebrew PATH.
    node = shutil.which('node') or shutil.which(
        'node', path=os.pathsep.join(('/opt/homebrew/bin', '/usr/local/bin'))
    )
    if not node:
        raise SystemExit('실험 뷰어를 실행하려면 Node.js가 필요합니다.')
    os.execv(node, [node, str(Path(__file__).with_suffix('.mjs')), *sys.argv[1:]])


if __name__ == '__main__':
    main()
