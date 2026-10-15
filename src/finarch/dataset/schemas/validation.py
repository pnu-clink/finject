"""Shared Python schema validation for preparation and model responses.

Does not alter inputs, repair responses, or perform financial meaning checks.
Run this module to check a JSON file against a registered schema.
"""

traced = __import__('finarch.shared.run_logging.logging', fromlist=['traced']).traced
import argparse
import json
from pathlib import Path
from pydantic import ValidationError
from finarch.dataset.schemas.registry import CONTRACTS, describe, resolve_schema_id


@traced("python")
def parse_json(text):
    """Reject duplicate object keys and non-finite values rather than hide them."""
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("DUPLICATE_JSON_KEY: " + key)
            result[key] = value
        return result

    def reject(value):
        raise ValueError("NON_FINITE_JSON_NUMBER: " + value)

    return json.loads(text, object_pairs_hook=pairs, parse_constant=reject)


@traced("python")
def parse_json_object(text):
    result = parse_json(text)
    if not isinstance(result, dict):
        raise ValueError("JSON_OBJECT_REQUIRED")
    return result


# [SC06] docs/02-architecture.md#SC06 — 스키마 원정의로 엄격히 검사하고 보정 없이 원래 값을 반환합니다.
@traced("python")
def validate(schema_id, value):
    schema_id = resolve_schema_id(schema_id)
    if schema_id not in CONTRACTS:
        raise ValueError("UNKNOWN_SCHEMA: " + schema_id)
    # Return the original value. Do not insert defaults or normalize types.
    CONTRACTS[schema_id].model.model_validate(value, strict=True)
    return value


@traced("python")
def check_json(schema_id, text):
    definition = describe(schema_id)
    report = {"schema_id": schema_id, "version": definition["version"],
              "schema_sha256": definition["sha256"], "readiness": definition["readiness"],
              "scope": "schema and declared Python validators; not semantic certification"}
    try:
        value = parse_json(text)
    except (ValueError, TypeError) as error:
        return {**report, "status": "FAIL", "reason": "JSON_INVALID", "error": str(error)}
    try:
        validate(schema_id, value)
    except ValidationError as error:
        return {**report, "status": "FAIL", "reason": "SCHEMA_INVALID",
                "errors": error.errors(include_input=False, include_url=False, include_context=False)}
    return {**report, "status": "PASS"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", choices=tuple(CONTRACTS), required=True)
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = check_json(args.schema, args.input.read_bytes())
    except OSError as error:
        report = {"schema_id": args.schema, "status": "FAIL", "reason": "INPUT_READ_ERROR",
                  "error": str(error)}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
