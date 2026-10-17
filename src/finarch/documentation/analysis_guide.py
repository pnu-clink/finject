"""Extract existing evidence for the Analysis guide without model calls."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN_ID = "20260927-exp-007-luna"
SOURCE = ROOT / "reports/experiments-run" / RUN_ID
OUTPUT = ROOT / "reports/run/20260928-analysis-guide"
GUIDE = "docs/02-experiments/02_analysis/00-overview.md"


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def rows(path):
    with path.open() as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def build():
    """AG01 read, AG02 verify, AG03 publish evidence and viewer navigation."""
    relative_sources = [
        "00_input/public.jsonl", "00_input/private.jsonl",
        "01_evaluation/02_request/luna-api/manifest.jsonl",
        "01_evaluation/04_validation/luna-api/results.jsonl",
        "01_evaluation/04_validation/numeric-comparisons.jsonl",
        "02_analysis/01_results/responses.jsonl", "02_analysis/01_results/state.json",
        "02_analysis/02_comparison/interpretations.jsonl",
    ]
    sources = []

    def record(path, role):
        sources.append({"path": path.relative_to(ROOT).as_posix(),
                        "sha256": digest(path), "role": role})

    for relative in relative_sources:
        record(SOURCE / relative, "Existing experimental evidence")
    counts, case_rows, identities = Counter(), {}, set()
    for row in rows(SOURCE / relative_sources[5]):
        require(row["response_id"] not in identities, "DUPLICATE_RESPONSE_ID")
        identities.add(row["response_id"])
        counts[row["status"]] += 1
        if row["case"] == "test-0381":
            case_rows[row["response_id"]] = row
    require(dict(counts) == {"VALID": 17812, "INVALID_RESPONSE": 12},
            "GUIDE_COUNTS_REQUIRE_EDITORIAL_REVIEW")
    state = json.loads((SOURCE / relative_sources[6]).read_text())
    require(state["planned"] == 17824 and state["statuses"] == dict(counts), "A01_STATE_MISMATCH")
    selected = []
    for variant in ("ORIGINAL", "IC_VALUE_01_BEFORE"):
        for reasoning in ("off", "on"):
            matches = [r for r in case_rows.values() if r["variant"] == variant
                       and r["reasoning"] == reasoning and r["prompt_condition"] == "guided"
                       and r["model"] == "luna-api"]
            require(len(matches) == 1, "EXAMPLE_MISSING_OR_AMBIGUOUS")
            selected.append(matches[0])
    ids = {r["trial_id"] for r in selected}
    requests, request_count = {}, 0
    for row in rows(SOURCE / relative_sources[2]):
        request_count += 1
        if row["trial_id"] in ids:
            requests[row["trial_id"]] = row
    require(request_count == 17824, "PLANNED_REQUEST_COUNT_MISMATCH")
    results, result_counts = {}, Counter()
    for row in rows(SOURCE / relative_sources[3]):
        result_counts[row["status"]] += 1
        if row["trial_id"] in ids:
            results[row["trial_id"]] = row
    require(result_counts == counts, "EVALUATION_A01_COUNTS_MISMATCH")
    numeric = {r["trial_id"]: r for r in rows(SOURCE / relative_sources[4]) if r["trial_id"] in ids}
    examples = []
    for row in selected:
        raw_path = SOURCE / row["result_path"]
        record(raw_path, "Original saved result for a displayed example")
        raw = json.loads(raw_path.read_text())
        require(row["response"] == raw["response"] == results[row["trial_id"]]["response"],
                "RAW_RESPONSE_MISMATCH")
        require(row["status"] == raw["status"] == "VALID", "EXAMPLE_STATUS_MISMATCH")
        for key in ("case", "item_id", "variant", "prompt_condition", "reasoning"):
            require(requests[row["trial_id"]][key] == row[key], "REQUEST_CONDITION_MISMATCH:" + key)
        is_null = row["variant"] == "IC_VALUE_01_BEFORE" and row["reasoning"] == "on"
        require(row["response"]["answer"] == (None if is_null else 95.83), "GUIDE_ANSWER_CHANGED")
        require(row["response"]["classification"] == ("CONFLICT" if is_null else "ANSWERABLE"),
                "GUIDE_CLASSIFICATION_CHANGED")
        examples.append({**{k: row[k] for k in ("response_id", "case", "item_id", "variant", "model",
                                               "prompt_condition", "reasoning", "status", "response")},
                         "raw_result_path": raw_path.relative_to(ROOT).as_posix(),
                         "saved_numeric_record": numeric[row["trial_id"]]})
    item_ids = {r["item_id"] for r in selected}
    public = [r for r in rows(SOURCE / relative_sources[0]) if r["item_id"] in item_ids]
    private = [r for r in rows(SOURCE / relative_sources[1]) if r["item_id"] in item_ids]
    require(len(public) == len(private) == 2, "EXAMPLE_INPUT_LINK_MISSING")
    require(all("470" in r["context"] and "240" in r["context"] for r in public), "CONTEXT_CHANGED")
    variant_id = next(r["item_id"] for r in private if r["variant"] == "IC_VALUE_01_BEFORE")
    require("517.0" in next(r["context"] for r in public if r["item_id"] == variant_id), "VALUE_MISSING")
    observation = next(r for r in rows(SOURCE / relative_sources[7]) if r["id"] == "test-0381-O03")
    for excerpt in observation["excerpts"]:
        require(excerpt["quote"] in case_rows[excerpt["response_id"]]["response"][excerpt["field"]],
                "OBSERVATION_QUOTE_MISMATCH")

    documents = [GUIDE, "docs/02-experiments/02_analysis/README.md",
                 "docs/02-experiments/02_analysis/01_results/README.md",
                 "docs/02-experiments/02_analysis/02_comparison/README.md",
                 "docs/02-experiments/02_analysis/03_research/README.md",
                 "reports/run/20260928-analysis-guide/README.md"]
    for relative in documents:
        record(ROOT / relative, "Current guide or stage contract")
    record(ROOT / "docs/02-experiments/01_evaluation/04_validation/README.md", "Evaluation boundary")
    record(Path(__file__).resolve(), "Evidence extraction and verification")
    require(all(digest(ROOT / s["path"]) == s["sha256"] for s in sources), "SOURCE_CHANGED_DURING_BUILD")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    write_json(OUTPUT / "example-evidence.json", {
        "kind": "READING_GUIDE_EVIDENCE", "source_run": RUN_ID,
        "scope": "Existing evidence for explanation; not a new evaluation or analysis result",
        "planned": request_count, "statuses": dict(counts), "case": "test-0381",
        "public_inputs": public, "existing_private_metadata": private,
        "examples": examples, "existing_observation": observation, "new_model_calls": 0})
    write_json(OUTPUT / "sources.json", {"sources": sources})
    write_json(OUTPUT / "migration.json", [])
    catalog = [{"path": p, "title": (ROOT / p).read_text().splitlines()[0].removeprefix("# "),
                "sha256": digest(ROOT / p), "group": "I'm going to analyze."} for p in documents]
    references = {s["path"] for s in sources}
    references.update(f"reports/run/20260928-analysis-guide/{name}" for name in
                      ("example-evidence.json", "sources.json", "validation.json", "events.jsonl"))
    write_json(OUTPUT / "documentation.json", {
        "kind": "PIPELINE_DOCUMENTATION", "title": "Analysis is easy to understand.",
        "entry_document": GUIDE, "documents": catalog, "reference_files": sorted(references), "model_calls": 0,
        "navigation": [["Easy to follow.", GUIDE], ["A01 Collect", documents[2]], ["A02 Compared to", documents[3]],
                       ["A03 I'll explain.", documents[4]], ["Writing records", documents[5]]]})
    old = json.loads((OUTPUT / "validation.json").read_text()) if (OUTPUT / "validation.json").exists() else {}
    validation = {"status": "PASS", "scope": "Saved evidence identity and counts; not semantic validation",
                  "planned": request_count, "statuses": dict(counts), "examples": len(examples),
                  "raw_response_equality": True, "request_identity": True, "existing_observation_quotes": True,
                  "source_hashes_unchanged": True, "guide_sha256": digest(ROOT / GUIDE), "model_calls": 0,
                  "documentation_validation": old.get("documentation_validation", "PENDING"),
                  "ui_review": old.get("ui_review", {"status": "PENDING"})
                  if old.get("guide_sha256") == digest(ROOT / GUIDE) else {"status": "PENDING"},
                  "user_review": "NOT_CONFIRMED"}
    write_json(OUTPUT / "validation.json", validation)
    write_json(OUTPUT / "summary.json", {"kind": "PIPELINE_DOCUMENTATION", "documents": len(catalog),
                                        "status": "DOCUMENTATION_READY", "model_calls": 0})
    with (OUTPUT / "events.jsonl").open("a") as stream:
        stream.write(json.dumps({"time": datetime.now(timezone.utc).isoformat(), "action": "BUILD_GUIDE_EVIDENCE",
                                 "source_run": RUN_ID, "examples": len(examples), "model_calls": 0}) + "\n")
    print(json.dumps({"status": "PASS", "planned": request_count, "examples": len(examples),
                      "source_files": len(sources), "model_calls": 0}))


if __name__ == "__main__":
    build()
