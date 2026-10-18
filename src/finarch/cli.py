"""New project entry point. Only preparation has an implementation at transfer."""

import argparse
import json
from importlib import import_module
from pathlib import Path

prepare = import_module("finarch.dataset.00-input.build").prepare


def main():
    # [DP01] docs/02-architecture.md#DP01 Read the preparation of the enzyme and the opening options and send them to prepare.
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare", help="Create source-derived Q/C/A inputs without LLM calls")
    p.add_argument("--sources", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    size = p.add_mutually_exclusive_group(required=True)
    size.add_argument("--total", type=int, help="Total inputs in the fixed easy:medium:hard:TAT-QA ratio 3:2:1:4")
    size.add_argument("--per-source", type=int, help="Legacy equal-count mode")
    p.add_argument("--seed", required=True)
    custom = sub.add_parser("prepare-custom", help="Convert raw files with a local deterministic adapter")
    custom.add_argument("--adapter", type=Path, required=True)
    custom.add_argument("--input", type=Path, action="append", required=True,
                        help="Raw input file; repeat for multiple files, in deterministic order")
    custom.add_argument("--output", type=Path, required=True)
    custom.add_argument("--name", required=True, help="Dataset display name")
    args = parser.parse_args()
    try:
        if args.command == "prepare-custom":
            convert = import_module("finarch.dataset.00-input.custom").prepare
            result = convert(args.adapter, args.input, args.output, name=args.name)
        else:
            result = prepare(args.sources, args.output, args.per_source, args.seed, total=args.total)
    # [DP02] docs/02-architecture.md#DP02 The shutdown code is error-prepared. 1So, normal returns are shown as JSON abstractions.
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"PREPARATION_FAILED: {error}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
