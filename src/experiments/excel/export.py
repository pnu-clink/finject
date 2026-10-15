"""Read saved Evaluation/Analysis records and export repeatable H1/H2 workbooks.

No experiment function, collection command, provider, or model is invoked.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import InvalidOperation
from hashlib import sha256
from importlib import import_module
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.dont_write_bytecode = True
sys.path.insert(0, str(REPO / "src"))

VARIANTS = {
    "IC_VALUE_01_BEFORE": "IC-v1",
    "IC_VALUE_01_AFTER": "IC-v2",
    "IC_RELATION_01": "IC-R",
    "EA_01": "EA1",
    "EA_02": "EA2",
}
CONDITIONS = [("unguided", "off"), ("unguided", "on"),
              ("guided", "off"), ("guided", "on")]
COUNTS = ["NS", "NU", "AS", "AU", "ND", "AD", "F",
          "NU_MATCH", "NU_MISMATCH", "NU_UNKNOWN",
          "AU_U_U", "AU_S_U", "AU_U_S", "AU_D_U", "AU_U_D"]


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def unique(rows, key, name):
    result = {}
    for row in rows:
        value = row[key]
        if value in result:
            raise ValueError(f"DUPLICATE_{name}: {value}")
        result[value] = row
    return result


class Snapshot:
    """Record bytes actually read, and reject an in-place concurrent write."""

    def __init__(self):
        self.files = {}

    def read(self, path, optional=False, lines=False):
        path = Path(path).resolve()
        if not path.exists() and optional:
            return [] if lines else None
        before = path.stat()
        payload = path.read_bytes()
        after = path.stat()
        if (before.st_mtime_ns, before.st_size) != (after.st_mtime_ns, after.st_size):
            raise ValueError(f"SOURCE_CHANGED_WHILE_READING: {path}")
        digest = sha256(payload).hexdigest()
        if str(path) in self.files and self.files[str(path)]["sha256"] != digest:
            raise ValueError(f"SOURCE_CHANGED_BETWEEN_READS: {path}")
        self.files[str(path)] = {"sha256": digest, "size": len(payload),
                                 "mtime_ns": after.st_mtime_ns}
        return [json.loads(line) for line in payload.splitlines() if line.strip()] if lines else json.loads(payload)

    def assert_unchanged(self):
        for name, saved in self.files.items():
            stat = Path(name).stat()
            if (stat.st_size, stat.st_mtime_ns) != (saved["size"], saved["mtime_ns"]):
                raise ValueError(f"SOURCE_CHANGED_DURING_EXPORT: {name}; rerun the exporter")


def latest_result(folder, trial):
    paths = list((folder / "calls" / trial).glob("attempt-*/result.json"))
    return max(paths, key=lambda p: int(p.parent.name.split("-")[-1])) if paths else None


def classify(action, review_status, arv, dg, reference_match):
    """Return a coarse NASU cell and its exhaustive unsupported subdivision."""
    if action not in ("N", "A") or review_status != "COMPLETED":
        return "F", "NOT_REVIEWED"
    allowed = {"SUPPORTED", "UNSUPPORTED", "UNDETERMINED"}
    applicable = [dg] if action == "N" else [arv, dg]
    if any(v not in allowed for v in applicable):
        return "F", "INVALID_VERDICT"
    if "UNSUPPORTED" in applicable:
        if action == "N":
            detail = "MATCH" if reference_match is True else "MISMATCH" if reference_match is False else "UNKNOWN"
            return "NU", "NU_" + detail
        short = {"SUPPORTED": "S", "UNSUPPORTED": "U", "UNDETERMINED": "D"}
        return "AU", f"AU_{short[arv]}_{short[dg]}"
    if all(v == "SUPPORTED" for v in applicable):
        return action + "S", action + "S"
    return action + "D", action + "D"


def numeric_match(response, status, reference, compare):
    if status != "VALID" or not isinstance(response, dict) or "answer" not in response:
        return None
    if response["answer"] is None:
        return False
    try:
        return compare(response, reference)["matches"]
    except (KeyError, ValueError, TypeError, InvalidOperation):
        return None


def read_run(root, label, snapshot):
    contracts = import_module("finarch.experiments.02-analysis.contracts")
    compare = import_module("finarch.experiments.01-evaluation.04-validation.answer_format").compare_answer
    started = utcnow()
    config = snapshot.read(root / "config.json")
    private = unique(snapshot.read(root / "00_input/private.jsonl", lines=True), "item_id", "PRIVATE_ITEM")
    # Resolve reusable Evaluation files through the run's explicit provenance only.
    reuse = config.get("evaluation_reuse", {})
    evaluation_root = root.parent / reuse.get("source_run", root.name)

    def source(relative):
        candidate = root / relative
        return candidate if candidate.exists() else evaluation_root / relative

    inputs, originals = {}, {}
    for model in config["evaluation"]["models"]:
        model_key = model["key"]
        plans = snapshot.read(source(f"01_evaluation/02_request/{model_key}/manifest.jsonl"), lines=True)
        unique(plans, "trial_id", "EVALUATION_REQUEST")
        results = unique(snapshot.read(source(f"01_evaluation/04_validation/{model_key}/results.jsonl"),
                                       optional=True, lines=True), "trial_id", "EVALUATION_RESULT")
        if set(results) - {p["trial_id"] for p in plans}:
            raise ValueError("UNPLANNED_EVALUATION_RESULT")
        for plan in plans:
            if plan["variant"] not in (*VARIANTS, "ORIGINAL"):
                continue
            result = results.get(plan["trial_id"], {})
            fields = ("case", "item_id", "variant", "prompt_condition", "reasoning")
            if result and any(result.get(k) != plan[k] for k in fields):
                raise ValueError("EVALUATION_IDENTITY_MISMATCH")
            item = private[plan["item_id"]]
            original_id = item.get("original_item_id", item["item_id"])
            original = private[original_id]
            dataset = original.get("generated_metadata", {}).get("provenance", {}).get("dataset", "UNKNOWN")
            response = result.get("response")
            row = {k: plan[k] for k in fields}
            row.update(run=root.name, label=label, dataset=dataset, model=model_key,
                       target_model=model["model"], response_id=model_key + ":" + plan["trial_id"],
                       status=result.get("status", "NOT_RUN"), response=response,
                       original_item_id=original_id, reference=original.get("reference", {}),
                       semantic_answerability=item.get("semantic_answerability", "NOT_ESTABLISHED"))
            row["original_reference_match"] = numeric_match(response, row["status"], row["reference"], compare)
            row["action"] = ("A" if response["answer"] is None else "N") if (
                row["status"] == "VALID" and isinstance(response, dict) and "answer" in response) else "UNKNOWN"
            if row["response_id"] in inputs:
                raise ValueError("DUPLICATE_EVALUATION_RESPONSE")
            inputs[row["response_id"]] = row
            if row["variant"] == "ORIGINAL":
                key = model_key, original_id, row["prompt_condition"], row["reasoning"]
                if key in originals:
                    raise ValueError("DUPLICATE_ORIGINAL_CONDITION")
                match = row["original_reference_match"]
                row["cohort"] = "CORRECT" if match is True else "INCORRECT" if match is False else "UNKNOWN"
                originals[key] = row

    folder = root / "02_analysis/02_comparison"
    requests = snapshot.read(folder / "manifest.jsonl", optional=True, lines=True)
    unique(requests, "trial_id", "ANALYSIS_REQUEST")
    selected = {req["trial_id"]: latest_result(folder, req["trial_id"]) for req in requests}
    assessments, judge_counts, judge_models = {}, Counter(), set()
    for request in requests:
        trial = request["trial_id"]
        judge_models.add(f'{request["model"]} / {request.get("reasoning_effort", "unspecified")}')
        path = selected[trial]
        result = snapshot.read(path) if path else None
        call_status = result.get("status", "NOT_RUN") if result else "NOT_RUN"
        error = ""
        if result:
            frozen = snapshot.read(path.with_name("request.json"))
            if frozen != request:
                call_status, error = "REQUEST_MISMATCH", "Saved attempt differs from the A02 manifest."
            elif call_status == "VALID":
                errors = contracts.validate_response(result.get("response"), request)
                if errors:
                    call_status, error = "CONTRACT_FAILED", json.dumps(errors, ensure_ascii=False)
        judge_counts[call_status] += 1
        reviewed = result.get("response", {}).get("response_assessments", []) if call_status == "VALID" else []
        by_id = unique(reviewed, "response_id", "ASSESSMENT")
        for observed in request["input"]["responses"]:
            if observed["variant"] not in VARIANTS:
                continue
            rid = observed["response_id"]
            if rid in assessments:
                raise ValueError("DUPLICATE_A02_RESPONSE:" + rid)
            if rid not in inputs:
                raise ValueError("A02_RESPONSE_OUTSIDE_EVALUATION:" + rid)
            target = inputs[rid]
            identity = ("item_id", "case", "variant", "model", "prompt_condition", "reasoning")
            if any(target[k] != observed[k] for k in identity):
                raise ValueError("A02_IDENTITY_MISMATCH:" + rid)
            assessment = by_id.get(rid)
            material = contracts.review_status(observed, request)
            review = assessment["review_status"] if assessment else (
                material if material != "COMPLETED" else "NOT_REVIEWED" if call_status == "NOT_RUN" else "REVIEW_FAILED")
            # A revised target response must never inherit its previous judge verdict.
            if target["status"] != observed["status"] or target["response"] != observed.get("response"):
                assessment, review = None, "STALE_TARGET"
            assessments[rid] = {"review_status": review,
                "arv": (assessment or {}).get("abstention_reason_validity", {}).get("verdict"),
                "dg": (assessment or {}).get("decision_grounding", {}).get("verdict"),
                "judge_status": call_status, "judge_model": request["model"],
                "judge_effort": request.get("reasoning_effort"), "analysis_trial": trial,
                "analysis_result": str(path) if path else None,
                "analysis_sha256": snapshot.files[str(path.resolve())]["sha256"] if path else None,
                "validation_error": error}

    rows = []
    for row in inputs.values():
        if row["variant"] == "ORIGINAL":
            continue
        key = row["model"], row["original_item_id"], row["prompt_condition"], row["reasoning"]
        original = originals.get(key)
        if original is None:
            raise ValueError("ORIGINAL_CONDITION_NOT_PLANNED:" + str(key))
        fallback = "NOT_REVIEWABLE" if row["status"] != "VALID" else "NOT_REVIEWED"
        row.update(assessments.get(row["response_id"], {"review_status": fallback, "arv": None, "dg": None,
                                                       "judge_status": "NOT_RUN"}))
        row["cohort"] = original["cohort"]
        row["nasu"], row["detail"] = classify(row["action"], row["review_status"], row["arv"], row["dg"],
                                                row["original_reference_match"])
        # Keep the original response in immutable input files; the export retains IDs and classifications.
        row["answer"] = (row.pop("response") or {}).get("answer")
        row["reference"] = row["reference"].get("reference_answer")
        rows.append(row)
    counts = Counter((r["model"], r["original_item_id"], r["prompt_condition"], r["reasoning"]) for r in rows)
    if set(counts) != set(originals) or any(n != len(VARIANTS) for n in counts.values()):
        raise ValueError("INCOMPLETE_FIVE_VARIANT_PLAN: export requires five paired variants per original condition")
    changed = sum(latest_result(folder, t) != p for t, p in selected.items())
    metadata = {"run": root.name, "label": label, "root": str(root), "started": started, "finished": utcnow(),
                "evaluation_source_run": evaluation_root.name, "planned_variants": len(rows),
                "planned_originals": len(originals), "a02_requests": len(requests),
                "judge_counts": dict(judge_counts), "judge_models": sorted(judge_models),
                "newer_attempts_during_read": changed, "new_model_calls": 0}
    original_records = [{k: r[k] for k in ("run", "label", "dataset", "model", "prompt_condition", "reasoning",
                        "item_id", "status", "action", "cohort")} for r in originals.values()]
    return rows, original_records, metadata


def aggregate(rows, originals):
    grouped, original_groups = defaultdict(list), defaultdict(list)
    for row in rows:
        key = tuple(row[k] for k in ("run", "label", "dataset", "model", "prompt_condition", "reasoning", "cohort", "variant"))
        grouped[key].append(row)
    for row in originals:
        key = tuple(row[k] for k in ("run", "label", "dataset", "model", "prompt_condition", "reasoning", "cohort"))
        original_groups[key].append(row)
    output = []
    for key, values in grouped.items():
        record = dict(zip(("run", "label", "dataset", "model", "prompt_condition", "reasoning", "cohort", "variant"), key))
        counter = Counter(r["nasu"] for r in values)
        details = Counter(r["detail"] for r in values)
        record.update({k: counter[k] if k in ("NS", "NU", "AS", "AU", "ND", "AD", "F") else details[k] for k in COUNTS})
        record.update(planned=len(values), original_count=len(original_groups[key[:-1]]))
        assert sum(record[k] for k in COUNTS[:7]) == record["planned"]
        assert sum(record[k] for k in ("NU_MATCH", "NU_MISMATCH", "NU_UNKNOWN")) == record["NU"]
        assert sum(record[k] for k in ("AU_U_U", "AU_S_U", "AU_U_S", "AU_D_U", "AU_U_D")) == record["AU"]
        assert record["planned"] == record["original_count"]
        output.append(record)
    return sorted(output, key=lambda r: (r["run"], r["model"], CONDITIONS.index((r["prompt_condition"], r["reasoning"])),
                                         r["cohort"], list(VARIANTS).index(r["variant"])))


def extract(entries, repo):
    snapshot, rows, originals, runs = Snapshot(), [], [], []
    if not entries:
        raise ValueError("NO_RUNS_SELECTED")
    names = [entry["run"] for entry in entries]
    if len(names) != len(set(names)):
        raise ValueError("DUPLICATE_RUN")
    if "20261003-exp-004-tatqa-luna" in names:
        raise ValueError("SUPERSEDED_LUNA_RUN: use 20261003-exp-004-tatqa-luna-sol-low")
    for entry in entries:
        root = (repo / "reports/experiments-run" / entry["run"]).resolve()
        print(f'Reading {entry["label"]}: {root.name}', flush=True)
        r, o, m = read_run(root, entry["label"], snapshot)
        rows.extend(r)
        originals.extend(o)
        runs.append(m)
        print(f'  {len(r):,} variant responses; A02 {m["judge_counts"]}', flush=True)
    snapshot.assert_unchanged()
    return {"schema_version": 1, "generated_at": utcnow(), "variants": VARIANTS,
            "rules": {"H1": "NASU across all planned originals", "H2": "Original correct versus incorrect, same model and condition",
                      "selected_numeric": "NS / (NS + NU_MISMATCH)", "selected_abstention": "AS / (AS + AU_U_U)",
                      "reference_basis": "ORIGINAL_REFERENCE_ONLY", "answerability_gold": "NOT_INFERRED",
                      "ic_source": "EXCLUDED_REQUIRES_SEPARATE_OVS_ANALYSIS"},
            "runs": runs, "aggregates": aggregate(rows, originals), "originals": originals,
            "responses": rows, "sources": snapshot.files, "new_model_calls": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=HERE / "runs.json")
    parser.add_argument("--run", action="append", help="Override the registered runs; repeat for multiple runs")
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--output", type=Path, default=REPO / "outputs/rq-excel/rq-results.xlsx")
    parser.add_argument("--data-only", action="store_true", help="Verify and extract without creating a workbook")
    parser.add_argument("--preview-dir", type=Path, help="Optionally render all worksheet opening views")
    args = parser.parse_args()
    entries = json.loads(args.config.read_text())["runs"]
    if args.run:
        labels = {e["run"]: e["label"] for e in entries}
        entries = [{"run": name, "label": labels.get(name, name)} for name in args.run]
    data = extract(entries, args.repo.resolve())
    output = args.output.resolve()
    if output.suffix.lower() != ".xlsx":
        raise ValueError("OUTPUT_MUST_BE_XLSX")
    if output.is_relative_to((args.repo / "reports/experiments-run").resolve()):
        raise ValueError("DO_NOT_WRITE_INSIDE_EXPERIMENT_RUNS")
    output.parent.mkdir(parents=True, exist_ok=True)
    runtime = Path(os.environ.get("CODEX_WORKSPACE_DEPENDENCIES", str(Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies")))
    with tempfile.TemporaryDirectory(prefix="rq-excel-") as temp:
        work = Path(temp)
        payload = work / "data.json"
        payload.write_text(json.dumps(data, ensure_ascii=False, allow_nan=False))
        if not args.data_only:
            node, modules = runtime / "node/bin/node", runtime / "node/node_modules"
            if not node.exists() or not (modules / "@oai/artifact-tool").exists():
                raise RuntimeError("Bundled artifact-tool unavailable; set CODEX_WORKSPACE_DEPENDENCIES")
            (work / "node_modules").symlink_to(modules, target_is_directory=True)
            shutil.copyfile(HERE / "workbook.mjs", work / "workbook.mjs")
            command = [str(node), "--max-old-space-size=8192", str(work / "workbook.mjs"), str(payload), str(work / "result.xlsx")]
            if args.preview_dir:
                command.extend(["--preview-dir", str(args.preview_dir.resolve())])
            subprocess.run(command, check=True)
            # Publish complete exports atomically, never an incomplete workbook.
            temporary = output.with_suffix(".tmp.xlsx")
            shutil.copyfile(work / "result.xlsx", temporary)
            os.replace(temporary, output)
        data_path = output.with_suffix(".data.json")
        temporary = data_path.with_suffix(".tmp.json")
        shutil.copyfile(payload, temporary)
        os.replace(temporary, data_path)
    print(json.dumps({"xlsx": str(output) if not args.data_only else None,
                      "data": str(data_path), "variant_responses": len(data["responses"]),
                      "new_model_calls": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
