#!/usr/bin/env python3
"""Validate the public FInject final release files."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


EXPECTED_CATEGORIES = {
    "EA-partial",
    "EA-full",
    "SA",
    "IC-value",
    "IC-source",
    "IC-premise",
}

REQUIRED_FIELDS = {
    "sample_id",
    "source_qid",
    "category",
    "generator_model",
    "question",
    "original_context",
    "perturbed_context",
    "origin_ground_truth",
    "origin_python_solution",
    "gold_label_solvable",
    "gold_label_category",
}


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{line_no}: invalid JSON: {exc}") from exc
    return rows


def json_type_ok(value: Any, expected: str | list[str]) -> bool:
    if isinstance(expected, str):
        expected = [expected]
    checks = {
        "string": lambda v: isinstance(v, str),
        "number": lambda v: (isinstance(v, (int, float)) and not isinstance(v, bool)),
        "integer": lambda v: (isinstance(v, int) and not isinstance(v, bool)),
        "boolean": lambda v: isinstance(v, bool),
        "array": lambda v: isinstance(v, list),
        "object": lambda v: isinstance(v, dict),
        "null": lambda v: v is None,
    }
    return any(checks[t](value) for t in expected)


def validate_schema(rows: list[dict], schema_path: Path) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    required = set(schema.get("required", []))
    properties = schema.get("properties", {})
    allow_extra = schema.get("additionalProperties", True)
    for i, row in enumerate(rows):
        missing = required - row.keys()
        if missing:
            raise SystemExit(f"Row {i} missing schema-required fields: {sorted(missing)}")
        if not allow_extra:
            extra = set(row) - set(properties)
            if extra:
                raise SystemExit(f"Row {i} has schema-extra fields: {sorted(extra)}")
        for key, value in row.items():
            prop = properties.get(key)
            if not prop or "type" not in prop:
                continue
            if not json_type_ok(value, prop["type"]):
                raise SystemExit(
                    f"Row {i} field {key!r} has type {type(value).__name__}, "
                    f"expected {prop['type']}"
                )
            if "enum" in prop and value not in prop["enum"]:
                raise SystemExit(f"Row {i} field {key!r} has value outside enum: {value!r}")
            if "const" in prop and value != prop["const"]:
                raise SystemExit(f"Row {i} field {key!r} does not match const {prop['const']!r}")


def validate(rows: list[dict]) -> None:
    if len(rows) != 426:
        raise SystemExit(f"Expected 426 rows, found {len(rows)}")

    sample_ids = [row.get("sample_id") for row in rows]
    duplicate_ids = [sid for sid, count in Counter(sample_ids).items() if count > 1]
    if duplicate_ids:
        raise SystemExit(f"Duplicate sample_id values: {duplicate_ids[:10]}")

    for i, row in enumerate(rows):
        missing = REQUIRED_FIELDS - row.keys()
        if missing:
            raise SystemExit(f"Row {i} missing required fields: {sorted(missing)}")
        if row["category"] not in EXPECTED_CATEGORIES:
            raise SystemExit(f"Row {i} has unknown category: {row['category']}")
        if row["gold_label_category"] != row["category"]:
            raise SystemExit(f"Row {i} category/gold_label_category mismatch")
        if row["gold_label_solvable"] is not False:
            raise SystemExit(f"Row {i} gold_label_solvable must be false")
        if not row["question"].strip() or not row["perturbed_context"].strip():
            raise SystemExit(f"Row {i} has empty question or perturbed_context")

    category_counts = Counter(row["category"] for row in rows)
    if set(category_counts) != EXPECTED_CATEGORIES:
        raise SystemExit(f"Category set mismatch: {dict(category_counts)}")
    bad_counts = {cat: count for cat, count in category_counts.items() if count != 71}
    if bad_counts:
        raise SystemExit(f"Expected 71 rows per category, found: {bad_counts}")

    print("FInject validation passed.")
    print(f"Rows: {len(rows)}")
    print(f"Categories: {dict(sorted(category_counts.items()))}")
    print(f"Source problems: {len(set(row['source_qid'] for row in rows))}")
    print(f"Generators: {dict(sorted(Counter(row['generator_model'] for row in rows).items()))}")


def validate_controls(path: Path, final_rows: list[dict]) -> None:
    if not path.exists():
        raise SystemExit(f"Missing original controls file: {path}")
    controls = load_jsonl(path)
    schema_path = path.with_name("schema.json")
    if schema_path.exists():
        validate_schema(controls, schema_path)
    if len(controls) != 78:
        raise SystemExit(f"Expected 78 original controls, found {len(controls)}")
    control_qids = {row.get("source_qid") for row in controls}
    final_qids = {row["source_qid"] for row in final_rows}
    if control_qids != final_qids:
        raise SystemExit("Original controls source_qid set does not match final release")
    for i, row in enumerate(controls):
        required = {
            "control_id",
            "source_dataset",
            "source_qid",
            "question",
            "original_context",
            "origin_ground_truth",
            "origin_python_solution",
            "gold_label_solvable",
        }
        missing = required - row.keys()
        if missing:
            raise SystemExit(f"Control row {i} missing required fields: {sorted(missing)}")
        if row["gold_label_solvable"] is not True:
            raise SystemExit(f"Control row {i} gold_label_solvable must be true")
    print(f"Original controls: {len(controls)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "dataset",
        nargs="?",
        default="data/final_release/finject_final_426.jsonl",
        help="Path to finject_final_426.jsonl",
    )
    parser.add_argument(
        "--controls",
        default="data/original_controls/finject_original_controls_78.jsonl",
        help="Path to finject_original_controls_78.jsonl",
    )
    args = parser.parse_args()
    dataset_path = Path(args.dataset)
    rows = load_jsonl(dataset_path)
    schema_path = dataset_path.with_name("schema.json")
    if schema_path.exists():
        validate_schema(rows, schema_path)
    validate(rows)
    validate_controls(Path(args.controls), rows)


if __name__ == "__main__":
    main()
