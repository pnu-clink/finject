"""New project entry point. Only preparation has an implementation at transfer."""

import argparse
import json
from importlib import import_module
from pathlib import Path

prepare = import_module("finarch.dataset.00-input.build").prepare


def main():
    # [DP01] docs/02-architecture.md#DP01 — 준비 인자·개수 옵션을 읽어 prepare에 전달합니다.
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare", help="Create source-derived Q/C/A inputs without LLM calls")
    p.add_argument("--sources", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    size = p.add_mutually_exclusive_group(required=True)
    size.add_argument("--total", type=int, help="Total inputs in the fixed easy:medium:hard:TAT-QA ratio 3:2:1:4")
    size.add_argument("--per-source", type=int, help="Legacy equal-count mode")
    p.add_argument("--seed", required=True)
    args = parser.parse_args()
    try:
        result = prepare(args.sources, args.output, args.per_source, args.seed, total=args.total)
    # [DP02] docs/02-architecture.md#DP02 — 준비 오류는 종료 코드 1, 정상 반환은 JSON 요약으로 표시합니다.
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"PREPARATION_FAILED: {error}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
