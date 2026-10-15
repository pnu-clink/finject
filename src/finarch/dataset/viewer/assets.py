"""Assemble the shared viewer from menu-owned sources, without reading run data."""
from pathlib import Path
import re
from finarch.paths import VIEWER, SOURCE

CODE = Path(__file__).resolve().parent
ROOT = VIEWER / "dataset"
SHARED = VIEWER / "shared"
OUTPUT = ROOT / "index.html"
INCLUDE = re.compile(r"/\* @include ([\w./-]+) \*/")


def render():
    def expand(source, chain=()):
        def include(match):
            path = (ROOT / match[1]).resolve()
            if not (path.is_relative_to(ROOT) or path.is_relative_to(SHARED)) or path in chain:
                raise ValueError(f"Invalid viewer include: {match[1]}")
            return expand(path.read_text(), (*chain, path)).rstrip()
        return INCLUDE.sub(include, source)
    return expand((ROOT / "shell.html").read_text())


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(render())
    template = SOURCE / 'documentation/templates/source-layout/dataset-viewer.md'
    (CODE / 'README.md').write_text(template.read_text())
    print(f"Updated shared viewer: {OUTPUT}")


if __name__ == "__main__":
    main()
