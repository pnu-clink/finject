"""Bundle a documented dataset survey for the shared viewer without model calls."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = (Path(__file__).resolve().parent / '../../../..').resolve()
TEMPLATE = Path(__file__).with_name("dataset-survey-readme-template.md")


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def bundle(run):
    run = run.resolve()
    if not run.is_relative_to(ROOT / "reports" / "run"):
        raise ValueError("Survey directory must be under reports/run")
    catalog = json.loads((run / "candidates.json").read_text(encoding="utf-8"))
    documents = sorted((run / "docs").glob("*.md"))
    if not documents or not catalog["candidates"]:
        raise ValueError("Survey documents and candidates are required")
    inspection = json.loads((run / "inspection.json").read_text(encoding="utf-8"))
    for candidate in catalog["candidates"]:
        key = candidate.get("inspection_key")
        if key and inspection[key].get("rows", inspection[key].get("task_view_rows")) != candidate["public_rows"]:
            raise ValueError(f"Count mismatch: {candidate['id']}")
    records = [json.loads(line) for line in (run / "research-log.jsonl").read_text().splitlines() if line.strip()]
    verified = 0
    for record in records:
        if record.get("status") != 200 or not record.get("sha256"):
            continue
        relative = Path(record["path"])
        path = ((ROOT if relative.parts[:2] == ("reports", "run") else run) / relative).resolve()
        if not path.is_relative_to(run) or hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError(f"Evidence hash mismatch: {record['path']}")
        verified += 1
    values = {
        "AS_OF": catalog["as_of"], "WINDOW_START": catalog["window_start"],
        "CANDIDATES": str(len(catalog["candidates"])), "RUN_ID": run.name,
        "DOCUMENTS": "".join(f"\n---\n\n## {path.name}\n\n{path.read_text(encoding='utf-8')}\n" for path in documents),
    }
    readme = TEMPLATE.read_text(encoding="utf-8")
    for key, value in values.items():
        readme = readme.replace("{{" + key + "}}", value)
    (run / "README.md").write_text(readme, encoding="utf-8")
    now = datetime.now(timezone.utc).isoformat()
    summary = {
        "kind": "DATASET_SURVEY", "status": "RESEARCH_COMPLETE", "title": "Recently. 1QA data set survey",
        "as_of": catalog["as_of"], "window_start": catalog["window_start"], "updated_at": now,
        "candidates": len(catalog["candidates"]), "documents": len(documents),
        "count_verified": sum(c["count_basis"] != "PAPER_REPOSITORY_CLAIM" for c in catalog["candidates"]),
        "model_calls": 0, "model_experiments_run": False, "user_review": "NOT_CONFIRMED",
    }
    write_json(run / "summary.json", summary)
    checks_path = run / "checks.json"
    checks = json.loads(checks_path.read_text()) if checks_path.exists() else {}
    checks.update(bundle_status="PASS", count_crosschecks="PASS", evidence_hashes_verified=verified,
                  documents=len(documents), model_experiments="NOT_RUN", user_review="NOT_CONFIRMED")
    checks.setdefault("viewer", {"status": "PENDING"})
    write_json(checks_path, checks)
    manifest = []
    for path in sorted(run.rglob("*")):
        if path.is_file() and path.name not in {"manifest.json", "events.jsonl", "checks.json"}:
            data = path.read_bytes()
            manifest.append({"path": path.relative_to(run).as_posix(), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    write_json(run / "manifest.json", {"created_at": now, "files": manifest})
    with (run / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"at": now, "event": "SURVEY_BUNDLED", "documents": len(documents), "evidence_hashes_verified": verified}) + "\n")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    bundle(parser.parse_args().run)
