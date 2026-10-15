"""Bundle real run artifacts into an offline HTML; no network dependencies."""
import argparse
import hashlib
import json
from pathlib import Path


TEMPLATE = (Path(__file__).resolve().parent / '../../../..').resolve() / "viewer" / "dataset" / "index.html"


def collect(run_path, *, allow_partial=False, artifact_filter=None):
    root = Path(run_path).resolve()
    artifacts, hashes = {}, {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink() or path.suffix not in (".json", ".jsonl", ".mmd", ".md", ".txt", ".py"):
            continue
        if not path.resolve().is_relative_to(root):
            continue
        relative = path.relative_to(root).as_posix()
        if artifact_filter is not None and not artifact_filter(relative):
            continue
        if relative.startswith("06-human-review/02-record-decision/"):
            continue
        raw = path.read_bytes()
        hashes[relative] = hashlib.sha256(raw).hexdigest()
        try:
            text = raw.decode("utf-8")
            artifacts[relative] = json.loads(text) if path.suffix == ".json" else text
        except (UnicodeError, ValueError) as error:
            artifacts[relative] = {"read_error": str(error)}
    from finarch.dataset.viewer.stage_flow import build_flow
    stage_flow=build_flow(artifacts)
    viewer_aliases = __import__('finarch.dataset.90-operations.stage_paths', fromlist=['viewer_aliases']).viewer_aliases
    artifact_aliases=viewer_aliases(artifacts)
    for key in list(artifacts):
        if key.startswith('05-human-review/'):
            renamed = key.replace('05-human-review/', '07-human-review/', 1)
            if renamed not in artifacts:
                artifacts[renamed] = artifacts[key]
                artifact_aliases[renamed] = key
    # Present the renamed preparation stage while preserving physical paths and hashes.
    for key in list(artifacts):
        if key.startswith('02-audit-meaning/'):
            renamed=key.replace('02-audit-meaning/','02-review-and-correct/',1)
            if renamed not in artifacts:
                artifacts[renamed]=artifacts.pop(key)
                artifact_aliases[renamed]=key

    from finarch.dataset.viewer.preparation_paths import add_read_aliases
    add_read_aliases(artifacts, artifact_aliases)

    if "run.json" not in artifacts:
        if not allow_partial:
            raise ValueError(f"RUN_JSON_REQUIRED: {root}")
        artifacts['run.json'] = {'status':'INCOMPLETE', 'events':[], 'note':'종료 기록 없음: 실행 중이거나 중단됐을 수 있습니다.' }
    fingerprint = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    candidate_current = __import__('finarch.dataset.02-generation.05-human-review.human_review', fromlist=['candidate_current']).candidate_current
    reviews=artifacts.get('06-human-review/03-result.json',[])
    known={r['variant']:r for r in reviews}
    for r in reviews:
        if r.get('review_sha256'):
            r['current']=candidate_current(root,r)
            if not r['current']:r.update(status='NOT_EVALUATED',reason='검토 대상 제작 자료가 변경되어 다시 검토해야 합니다.')
    decisions = {}
    decision_dir = root / "06-human-review/02-record-decision"
    for path in sorted(decision_dir.glob("*.json")):
        stored = json.loads(path.read_text())
        for decision in stored.get("decisions", []):
            review=known.get(decision.get('variant'),{})
            valid=(decision.get('review_sha256')==review.get('review_sha256') and review.get('current')) if decision.get('review_sha256') else stored.get('snapshot_sha256')==fingerprint
            if valid:decisions[decision['variant']]=decision
    return {"path": str(root), "snapshot_sha256": fingerprint, "artifacts": artifacts, "decisions": decisions, "stage_flow":stage_flow,"artifact_aliases":artifact_aliases}


# [BI07] docs/02-architecture.md#BI07 — 기존 문제별 실행 결과를 모아 비교 HTML을 만듭니다. 별도 내보내기 용도입니다. 기본 뷰어는 server.py가 실제 기록을 읽습니다.
def build(run_paths, output):
    roots = set()
    for value in run_paths:
        path = Path(value).resolve()
        if (path / "run.json").is_file(): roots.add(path)
        else: roots.update(item.parent for item in path.rglob("run.json"))
    if not roots: raise ValueError("NO_RUNS_FOUND")
    payload = {"format": "fin-arch-viewer-v1", "auto_refresh":False,
               "runs": [collect(root) for root in sorted(roots)]}
    encoded = json.dumps(payload, ensure_ascii=False).replace("&", "\\u0026").replace("<", "\\u003c")
    encoded = encoded.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    html = TEMPLATE.read_text().replace("__FINARCH_DATA__", encoded)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream: stream.write(html)
    return {"output": str(output.resolve()), "runs": len(roots)}



# [H01] docs/02-architecture.md#H01 — 내보낸 사람 판정을 최신 snapshot과 대조해 새 이력에 반영하며 동결하지 않습니다.
# [R01] docs/02-architecture.md#R01 — 거절 판정도 같은 import_decisions 경로에서 새 이력으로 저장합니다.
def import_decisions(run_path, decision_path):
    """Import explicit human decisions only against the unchanged snapshot."""
    return record_decisions(run_path,json.loads(Path(decision_path).read_text()))


def record_decisions(run_path, payload):
    import datetime
    import uuid
    run = collect(run_path)
    decisions = payload.get("decisions")
    if not isinstance(decisions, list) or not decisions: raise ValueError("DECISIONS_REQUIRED")
    reviews = run["artifacts"].get("06-human-review/03-result.json", [])
    known = {item["variant"]: item for item in reviews}
    labels = set()
    for item in decisions:
        label = item.get("variant")
        if label not in known or label in labels: raise ValueError("UNKNOWN_OR_DUPLICATE_VARIANT")
        labels.add(label)
        if item.get('review_sha256'):
            if item['review_sha256']!=known[label].get('review_sha256') or not known[label].get('current'):
                raise ValueError('REVIEW_TARGET_CHANGED')
        elif payload.get('snapshot_sha256')!=run['snapshot_sha256']:
            raise ValueError('REVIEW_SNAPSHOT_CHANGED')
        if item.get("decision") not in ("APPROVE", "REVISE", "REJECT"):
            raise ValueError("INVALID_DECISION")
        if any(not isinstance(item.get(key), str) or not item[key].strip() for key in ("reviewer", "reason", "reviewed_at")):
            raise ValueError("REVIEWER_TIME_AND_REASON_REQUIRED")
        if item["decision"] == "APPROVE" and known[label].get("status") != "AWAITING_HUMAN":
            raise ValueError("CANNOT_APPROVE_UNREADY_CANDIDATE")
        if item["decision"] == "APPROVE" and run["artifacts"].get("demo.json", {}).get("demonstration"):
            raise ValueError("DEMONSTRATION_CANNOT_BE_APPROVED")
    directory = Path(run_path) / "06-human-review/02-record-decision"
    directory.mkdir(exist_ok=True)
    name = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%f") + "-" + uuid.uuid4().hex + ".json"
    target = directory / name
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return {"saved": str(target), "decisions": len(decisions), "frozen": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    view = sub.add_parser("build")
    view.add_argument("--runs", nargs="+", required=True)
    view.add_argument("--output", required=True)
    review = sub.add_parser("import-review")
    review.add_argument("--run", required=True)
    review.add_argument("--decisions", required=True)
    args = parser.parse_args()
    result = build(args.runs, args.output) if args.command == "build" else import_decisions(args.run, args.decisions)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__": main()
