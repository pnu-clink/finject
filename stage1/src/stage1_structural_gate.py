#!/usr/bin/env python3
"""Run the public FInject Stage 1 deterministic structural gate.

The paper describes Stage 1 as a structural screen: a candidate must satisfy the
required predicates for its intended category. Forbidden-pattern deductions are
reported as diagnostics and lower the score, following the supplementary
material, but they do not flip PASS by themselves.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from perturb.constants import TYPE_ORDER
from perturb.purpose_fit.scoring import score


def _field(row: dict, *names: str, default: str = "") -> str:
    for name in names:
        value = row.get(name)
        if value is not None:
            return str(value)
    return default


def evaluate_row(row: dict) -> dict:
    category = _field(row, "category", "gold_label_category")
    if category not in TYPE_ORDER:
        return {
            "sample_id": row.get("sample_id"),
            "category": category,
            "stage1_pass": False,
            "gate_failures": [f"unknown category: {category}"],
            "forbidden_patterns": [],
            "purpose_score": 0.0,
        }

    original_context = _field(row, "original_context", "context_original", "context")
    perturbed_context = _field(row, "perturbed_context", "transformed_context")
    python_solution = _field(row, "origin_python_solution", "python_solution", "solution")
    question = _field(row, "question")

    if not perturbed_context.strip():
        return {
            "sample_id": row.get("sample_id"),
            "category": category,
            "stage1_pass": False,
            "gate_failures": ["empty perturbed_context"],
            "forbidden_patterns": [],
            "purpose_score": 0.0,
        }

    gates_ok, gate_failures, forbidden_patterns, details = score(
        category, original_context, perturbed_context, python_solution, question
    )

    # Public Stage 1 follows the submitted supplementary material: PASS/FAIL is
    # decided by required gates; deductions lower the diagnostic score.
    stage1_pass = bool(gates_ok)

    return {
        "sample_id": row.get("sample_id"),
        "source_qid": row.get("source_qid"),
        "category": category,
        "stage1_pass": stage1_pass,
        "gate_failures": gate_failures,
        "forbidden_patterns": forbidden_patterns,
        "purpose_score": details.get("purpose_score", 0.0),
        "score_breakdown": details.get("breakdown", {}),
    }


def load_json_or_jsonl(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text[0] == "[":
        data = json.loads(text)
        if not isinstance(data, list):
            raise SystemExit(f"{path}: expected a JSON array or JSONL file")
        return data
    rows = []
    for line_no, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path}:{line_no}: invalid JSON: {exc}") from exc
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="candidate JSON or JSONL file")
    parser.add_argument("--output", help="optional JSONL audit output path")
    args = parser.parse_args()

    rows = load_json_or_jsonl(Path(args.input))
    results = [evaluate_row(row) for row in rows]

    out = "\n".join(json.dumps(row, ensure_ascii=False) for row in results)
    if args.output:
        Path(args.output).write_text(out + ("\n" if out else ""), encoding="utf-8")
    else:
        sys.stdout.write(out + ("\n" if out else ""))

    passed = sum(1 for row in results if row["stage1_pass"])
    print(f"Stage 1 structural gate: {passed}/{len(results)} pass", file=sys.stderr)


if __name__ == "__main__":
    main()
