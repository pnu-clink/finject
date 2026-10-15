"""Audit every nonempty JSON context in pinned FinanceReasoning, without LLM calls."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib
import json
from pathlib import Path

from finarch.dataset.schemas.validation import validate
from finarch.shared.reference import load_raw

adapters = importlib.import_module("finarch.dataset.00-input.adapters")
converter = importlib.import_module("finarch.dataset.00-input.json_context")
ROOT = Path(__file__).resolve().parents[4]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def build(output, catalog=None):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    catalog = Path(catalog or ROOT / "config/source-catalog.json").resolve()
    summaries, rows, prepared, originals, checks, sources = {}, [], [], [], [], []
    inventory = Counter()
    shape_counts = Counter()
    for source in json.loads(catalog.read_text())["sources"]:
        if source["adapter"] != "finance":
            continue
        path = (catalog.parent / source["path"]).resolve()
        before = sha(path)
        if before != source["sha256"]:
            raise ValueError("RAW_SOURCE_HASH_MISMATCH:" + source["name"])
        records = load_raw(path.read_bytes())
        counts = Counter(source_total=len(records))
        provenance = {key: source[key] for key in ("name", "url", "commit", "sha256")}
        for index, record in enumerate(records):
            text = record.get("context")
            if not isinstance(text, str):
                counts["non_json_context"] += 1
                continue
            try:
                parsed = json.loads(text)
            except ValueError:
                counts["non_json_context"] += 1
                continue
            if not isinstance(parsed, (dict, list)):
                counts["non_json_context"] += 1
                continue
            if not parsed:
                counts["empty_json_context"] += 1
                continue
            counts["json_targets"] += 1
            raw_id = "finance-" + record["question_id"]
            originals.append({"raw_id": raw_id, "source_file": str(path.relative_to(ROOT)),
                              "source_index": index, "record": record})
            row = {"id": raw_id, "raw_id": raw_id, "source_file": str(path.relative_to(ROOT)),
                   "source_index": index, "question": record["question"], "original_context": text}
            try:
                sample = {"id": raw_id, **adapters.finance(record, provenance, distributed=True)}
                validate("prepared.input", [sample])
                check = converter.validate_conversion(text, sample)
                again = {"id": raw_id, **adapters.finance(record, provenance, distributed=True)}
                if again != sample:
                    raise ValueError("NONDETERMINISTIC_JSON_ADAPTER")
                if sample["question"] != record["question"]:
                    raise ValueError("QUESTION_CHANGED_BY_JSON_ADAPTER")
                expected = adapters.extract_reference(record["ground_truth"]).fields()
                if any(sample[key] != value for key, value in expected.items()):
                    raise ValueError("REFERENCE_CHANGED_BY_JSON_ADAPTER")
                shape = "object_tables" if isinstance(parsed, dict) else "array_table_string"
                shape_counts[shape] += 1
                row.update(status="PASS", shape=shape, sample=sample, check={
                    **check, "checks": [*check["checks"], "prepared_input_schema",
                                       "question_reference_preserved", "deterministic_output"]})
                prepared.append(sample)
                counts["passed"] += 1
            except Exception as error:
                row.update(status="FAIL", reason=type(error).__name__ + ":" + str(error))
                counts["failed"] += 1
            rows.append(row)
            checks.append({"raw_id": raw_id, "source_file": row["source_file"],
                           "source_index": index, "status": row["status"],
                           "check": row.get("check"), "reason": row.get("reason")})
        after = sha(path)
        if before != after:
            raise ValueError("RAW_SOURCE_CHANGED_DURING_CHECK")
        sources.append({"path": str(path.relative_to(ROOT)), "before_sha256": before,
                        "after_sha256": after, "unchanged": before == after})
        summaries[source["name"]] = dict(counts)
        inventory.update(counts)
    if prepared:
        validate("prepared.input", prepared)
    summary = {key: inventory[key] for key in
               ("source_total", "json_targets", "passed", "failed", "empty_json_context", "non_json_context")}
    report = {"format": "json-context-adapter-check-v1", "run_id": output.name,
              "created_at": datetime.now(timezone.utc).isoformat(),
              "status": "PASS" if summary["passed"] == summary["json_targets"] and not summary["failed"] else "FAIL",
              "model_calls": 0, "summary": summary, "by_source": summaries,
              "shapes": dict(shape_counts), "sources": sources, "records": rows,
              "scope": "JSON-to-table representation, type/span/schema preservation only; no semantic or model validation"}
    write(output / "json-context-adapter-check.json", report)
    write(output / "prepared-input.json", prepared)
    write(output / "raw-records.json", originals)
    write(output / "summary.json", {key: report[key] for key in
                                   ("format", "run_id", "status", "model_calls", "summary")})
    (output / "checks.jsonl").write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in checks))
    files = ["json-context-adapter-check.json", "prepared-input.json", "raw-records.json",
             "summary.json", "checks.jsonl"]
    template = ROOT / "src/finarch/documentation/templates/json-context-adapter-check.md"
    counts_table = "\n".join(f"|{name}|{c['source_total']}|{c.get('json_targets',0)}|{c.get('passed',0)}|"
                            f"{c.get('failed',0)}|{c.get('empty_json_context',0)}|" for name,c in summaries.items())
    replacements = {**{key: str(value) for key, value in summary.items()},
                    "run_id": output.name, "counts_table": counts_table}
    readme = template.read_text()
    for key, value in replacements.items():
        readme = readme.replace("{" + key + "}", value)
    (output / "README.md").write_text(readme)
    write(output / "manifest.json", {"kind": "JSON_CONTEXT_ADAPTER_CHECK", "sources": sources,
          "files": [{"path": name, "sha256": sha(output / name)} for name in [*files, "README.md"]],
          "model_calls": 0})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--catalog")
    args = parser.parse_args()
    report = build(args.output, args.catalog)
    print(json.dumps({**report["summary"], "status": report["status"], "model_calls": 0}))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
