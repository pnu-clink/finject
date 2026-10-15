"""Read saved experiment evidence for dashboards without altering any source file.

The cached payload is a read-only snapshot for callers. Missing metrics stay null;
zero is retained only when the saved result explicitly contains zero. No provider,
scorer, credential, usage-limit, or model-call code is imported here.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import threading
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_metrics_module = __import__('finarch.dashboard.02-metrics.metrics', fromlist=['*'])
_number, _metrics, _timing = _metrics_module._number, _metrics_module._metrics, _metrics_module._timing

ROOT = (Path(__file__).resolve().parent / '../../../..').resolve()
REPORT = Path("reports/run/20260923-experiment-improvement")
SOURCE_PATHS = {
    "rows": REPORT / "01-baseline/rows.jsonl",
    "summary": REPORT / "01-baseline/summary.json",
    "contrasts": REPORT / "03-research/contrasts.json",
    "review_evidence": REPORT / "03-research/intent-review-evidence.json",
    "a100": REPORT / "02-a100/source/summary.json",
    "execution": REPORT / "status.json",
}
TRIAL_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")
_LOCK = threading.RLock()
_CACHE: OrderedDict[Path, "_Snapshot"] = OrderedDict()
_MAX_PROJECTS = 3


@dataclass
class _Snapshot:
    signature: tuple
    payload: dict
    by_trial: dict


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _fixed_source(project: Path, relative: Path) -> Path:
    path = (project / relative).resolve()
    if not _within(path, project / "reports"):
        raise ValueError("UNSAFE_DASHBOARD_SOURCE_PATH")
    return path


def _registered_path(project: Path, row: dict, field: str) -> Path | None:
    """Resolve only a row's registered artifact, constrained to experiment runs."""
    value = row.get(field)
    if value is None:
        return None
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ValueError("INVALID_REGISTERED_ARTIFACT_PATH:" + field)
    path = (project / value).resolve()
    allowed = project / "reports/experiments-run"
    if path == allowed or not _within(path, allowed):
        raise ValueError("UNSAFE_REGISTERED_ARTIFACT_PATH:" + field)
    return path


def _signature(project: Path) -> tuple:
    states = []
    for relative in SOURCE_PATHS.values():
        path = _fixed_source(project, relative)
        try:
            stat = path.stat()
            states.append((str(path), stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size, stat.st_ino))
        except FileNotFoundError:
            states.append((str(path), None))
    return tuple(states)


def _read_json(path: Path, project: Path, hashes: dict, *, lines=False):
    raw = path.read_bytes()
    hashes[str(path.relative_to(project))] = hashlib.sha256(raw).hexdigest()
    if lines:
        return [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    return json.loads(raw)


def _optional_artifact(path: Path | None, project: Path, hashes: dict) -> dict | None:
    if path is None or not path.exists():
        return None
    value = _read_json(path, project, hashes)
    if not isinstance(value, dict):
        raise ValueError("ARTIFACT_OBJECT_REQUIRED:" + str(path.relative_to(project)))
    return value


def _input(call: dict | None) -> dict:
    request = call.get("request") if isinstance(call, dict) else None
    payload = request.get("input") if isinstance(request, dict) else None
    return payload if isinstance(payload, dict) else {}


def _build(project: Path) -> tuple[dict, dict]:
    hashes = {}
    sources = {name: _read_json(_fixed_source(project, relative), project, hashes, lines=name == "rows")
               for name, relative in SOURCE_PATHS.items()}
    original_rows = sources.pop("rows")
    if not isinstance(original_rows, list):
        raise ValueError("DASHBOARD_ROWS_REQUIRED")
    for name, source in sources.items():
        if not isinstance(source, dict):
            raise ValueError("DASHBOARD_SOURCE_OBJECT_REQUIRED:" + name)
    rows, by_trial = [], {}
    for original in original_rows:
        if not isinstance(original, dict):
            raise ValueError("DASHBOARD_ROW_OBJECT_REQUIRED")
        trial = original.get("trial_id")
        if not isinstance(trial, str) or not TRIAL_ID.fullmatch(trial):
            raise ValueError("INVALID_RECORDED_TRIAL_ID")
        if trial in by_trial:
            raise ValueError("DUPLICATE_RECORDED_TRIAL_ID")
        paths = {field: _registered_path(project, original, field)
                 for field in ("call_path", "result_path", "raw_path")}
        call = _optional_artifact(paths["call_path"], project, hashes)
        warnings = []
        if call is None:
            warnings.append("CALL_ARTIFACT_MISSING" if paths["call_path"] else "CALL_PATH_NOT_RECORDED")
        request = call.get("request") if isinstance(call, dict) else None
        if isinstance(request, dict) and request.get("trial_id") not in (None, trial):
            raise ValueError("REGISTERED_CALL_TRIAL_MISMATCH")
        result = call.get("result") if isinstance(call, dict) else None
        if call is not None and not isinstance(result, dict):
            warnings.append("CALL_RESULT_MISSING")
        question = _input(call).get("question")
        row = dict(original)
        row["metrics"] = _metrics(result)
        row["timing"], timing_warnings = _timing(result)
        warnings.extend(timing_warnings)
        row["question_preview"] = question[:160] if isinstance(question, str) else None
        row["data_warnings"] = warnings
        rows.append(row)
        by_trial[trial] = row
    summary = sources["summary"]
    planned = summary.get("overall", {}).get("planned")
    if type(planned) is int and planned != len(rows):
        raise ValueError("ROW_COUNT_DIFFERS_FROM_SAVED_PLANNED_DENOMINATOR")
    run_id, model = summary.get("run_id"), summary.get("model")
    if any(row.get("run_id") != run_id or row.get("model") != model for row in rows):
        raise ValueError("ROW_RUN_OR_MODEL_DIFFERS_FROM_SAVED_SUMMARY")
    a100 = dict(sources["a100"])
    a100["snapshot_at"] = sources["a100"].get("updated_at")
    a100["source_snapshot_only"] = True
    a100["live_state_verified"] = False
    payload = {
        "schema_version": 1,
        "run_id": run_id,
        "model": model,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_run": summary.get("source_run"),
        "rows": rows,
        "summary": summary,
        "contrasts": sources["contrasts"],
        "a100": a100,
        "execution": sources["execution"],
        "review_evidence": sources["review_evidence"],
        "source_files": sorted(hashes),
        "source_sha256": dict(sorted(hashes.items())),
        "new_model_calls": 0,
        "semantic_assessment": "NOT_SCORED",
        "data_warnings": [{"trial_id": row["trial_id"], "warnings": row["data_warnings"]}
                          for row in rows if row["data_warnings"]],
        "cache_policy": "Metadata source changes invalidate the snapshot; refresh also rereads frozen call artifacts.",
    }
    return payload, by_trial


def _snapshot(project: Path, refresh=False) -> _Snapshot:
    project = Path(project).resolve()
    with _LOCK:
        signature = _signature(project)
        cached = _CACHE.get(project)
        if not refresh and cached is not None and cached.signature == signature:
            _CACHE.move_to_end(project)
            return cached
        for _ in range(2):
            payload, by_trial = _build(project)
            after = _signature(project)
            if after == signature:
                snapshot = _Snapshot(after, payload, by_trial)
                _CACHE[project] = snapshot
                _CACHE.move_to_end(project)
                while len(_CACHE) > _MAX_PROJECTS:
                    _CACHE.popitem(last=False)
                return snapshot
            signature = after
        raise RuntimeError("DASHBOARD_SOURCES_CHANGED_DURING_READ")


def load_data(project: Path = ROOT, refresh=False) -> dict:
    """Return every saved row; callers must not mutate the cached snapshot."""
    return _snapshot(project, refresh=refresh).payload


def response_detail(trial_id, project: Path = ROOT) -> dict:
    """Read Q/C only from the selected row's registered call; no path parameter."""
    if not isinstance(trial_id, str) or not TRIAL_ID.fullmatch(trial_id):
        raise ValueError("INVALID_TRIAL_ID")
    project = Path(project).resolve()
    snapshot = _snapshot(project)
    if trial_id not in snapshot.by_trial:
        raise KeyError("UNKNOWN_TRIAL_ID")
    row = snapshot.by_trial[trial_id]
    paths = {field: _registered_path(project, row, field)
             for field in ("call_path", "result_path", "raw_path")}
    call = _optional_artifact(paths["call_path"], project, {})
    request = call.get("request") if isinstance(call, dict) else None
    if isinstance(request, dict) and request.get("trial_id") not in (None, trial_id):
        raise ValueError("REGISTERED_CALL_TRIAL_MISMATCH")
    payload = _input(call)
    return {
        "row": row,
        "question": payload.get("question") if isinstance(payload.get("question"), str) else None,
        "context": payload.get("context") if isinstance(payload.get("context"), str) else None,
        "response": row.get("response"),
        "raw_path": row.get("raw_path"),
        "result_path": row.get("result_path"),
        "call_path": row.get("call_path"),
    }
