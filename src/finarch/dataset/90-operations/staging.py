"""Sequential orchestration support, not a Python/LLM/graph implementation.

Handlers must implement the contracts in docs/12-pipeline-code-guide.md.
Missing handlers are recorded as NOT_IMPLEMENTED, never treated as a pass.
Behavior tests and external calls have not been run during the interview.
"""

Journal = __import__('finarch.shared.run_logging.logging', fromlist=['Journal']).Journal
traced = __import__('finarch.shared.run_logging.logging', fromlist=['traced']).traced

import copy
import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Literal, Mapping, Protocol

from pydantic import ValidationError
from finarch.dataset.schemas.registry import LLM_ROLES, describe, require_llm_schema, SchemaContractError
from finarch.dataset.schemas.validation import validate, parse_json


Status = Literal["PASS", "FAIL", "NOT_EVALUATED", "NOT_IMPLEMENTED"]


@dataclass(frozen=True)
class StepResult:
    status: Status
    reason: str
    data: dict = field(default_factory=dict)


class StepStopped(RuntimeError):
    def __init__(self, stage: str, step: str, result: StepResult):
        super().__init__(result.reason)
        self.stage, self.step, self.result = stage, step, result


Handler = Callable[[dict], StepResult]

class LLMHandler(Protocol):
    def __call__(self, payload: dict, *, response_schema: dict) -> StepResult: ...


PYTHON_HOOKS = frozenset({
    "python.input_integrity", "python.check", "python.apply_patches",
    "pot.execute", "dag.compile", "dag.validate_inverse", "dag.inject", "dag.check_target",
})


def json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()


@traced("python")
def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@traced("python")
def _load_legacy_case(input_path: Path) -> dict:
    """Check preparation links; this is integrity, not semantic certification."""
    input_path = input_path.resolve()
    preparation_root = input_path.parent.parent.parent
    if (preparation_root / "preparation-start.json").exists():
        result_path = preparation_root / "preparation-result.json"
        if not result_path.exists():
            raise ValueError("PREPARATION_NOT_COMPLETE")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        if result.get("status") != "PASS":
            raise ValueError("PREPARATION_NOT_COMPLETE")
        if result.get("manifest_sha256") != file_hash(preparation_root / "selection-manifest.json"):
            raise ValueError("PREPARATION_MANIFEST_HASH_MISMATCH")
    comparison_path = input_path.with_name("comparison.json")
    record_path = input_path.with_name("raw-record.json")
    sample = json.loads(input_path.read_text(encoding="utf-8"))
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    record = json.loads(record_path.read_text(encoding="utf-8"))
    required = ("id", "raw_id", "context", "question", "reference_answer",
                "reference_answer_type", "reference_precision")
    if any(key not in sample for key in required):
        raise ValueError("INCOMPLETE_INPUT")
    if any(not isinstance(sample[key], str) or not sample[key].strip()
           for key in ("id", "raw_id", "context", "question")):
        raise ValueError("INVALID_INPUT_TEXT")
    if comparison["input_sha256"] != file_hash(input_path):
        raise ValueError("PREPARATION_INPUT_HASH_MISMATCH")
    if comparison["raw_record_sha256"] != file_hash(record_path):
        raise ValueError("PREPARATION_RECORD_HASH_MISMATCH")
    if comparison["raw_id"] != sample["raw_id"]:
        raise ValueError("PREPARATION_RAW_ID_MISMATCH")
    source = comparison["source"]
    if file_hash(Path(source["path"])) != source["sha256"]:
        raise ValueError("ORIGINAL_SOURCE_HASH_MISMATCH")
    return {"sample": sample, "provider_record": record,
            "comparison": comparison, "input_path": str(input_path)}


class PreparedInputs:
    """Read and verify a canonical collection once; select individual inputs by ID."""
    @traced("python")
    def __init__(self, input_path: Path):
        # [DP14] docs/02-architecture.md#DP14 — 준비 완료 PASS·manifest 해시·기록된 스키마 식별자를 검사합니다.
        # [BI01] docs/02-architecture.md#BI01 — 통합 입력 무결성 확인의 기존 번호입니다. DP14·DP15에서 이어집니다.
        self.path = Path(input_path).resolve()
        root = self.path.parent
        result_path = root / "preparation-result.json"
        if not result_path.exists():
            raise ValueError("PREPARATION_NOT_COMPLETE")
        result = json.loads(result_path.read_text())
        if result.get("status") != "PASS":
            raise ValueError("PREPARATION_NOT_COMPLETE")
        manifest_path = root / "selection-manifest.json"
        if result.get("manifest_sha256") != file_hash(manifest_path):
            raise ValueError("PREPARATION_MANIFEST_HASH_MISMATCH")
        manifest = json.loads(manifest_path.read_text())
        recorded_schema = manifest.get("input_schema")
        if recorded_schema is not None:
            recorded_id = recorded_schema.get("schema_id")
            if recorded_id not in ("prepared.input", "01-preparation.01-source.prepared-input"):
                raise ValueError("PREPARATION_SCHEMA_VERSION_MISMATCH")
            current = describe(recorded_id)
            if any(recorded_schema.get(k) != current[k] for k in ("schema_id", "version", "sha256")):
                raise ValueError("PREPARATION_SCHEMA_VERSION_MISMATCH")
        # [DP15] docs/02-architecture.md#DP15 — 통합 입력을 한 번 읽어 해시·스키마·ID·원천을 확인하고 메모리에 둡니다.
        # [BI02] docs/02-architecture.md#BI02 — 전체 입력 1회 읽기의 기존 번호입니다.
        input_bytes = self.path.read_bytes()
        provider_bytes = (root / "provider-records.json").read_bytes()
        if hashlib.sha256(input_bytes).hexdigest() != manifest["input_file_sha256"]:
            raise ValueError("PREPARATION_INPUT_HASH_MISMATCH")
        if hashlib.sha256(provider_bytes).hexdigest() != manifest.get("provider_file_sha256"):
            raise ValueError("PREPARATION_RECORD_HASH_MISMATCH")
        samples = parse_json(input_bytes)
        validate("01-preparation.01-source.prepared-input", samples)
        self.providers = json.loads(provider_bytes)
        self.samples = {}
        required = ("id", "raw_id", "context", "question", "reference_answer",
                    "reference_answer_type", "reference_precision")
        for sample in samples:
            if any(k not in sample for k in required):
                raise ValueError("INCOMPLETE_INPUT")
            if any(not isinstance(sample[k], str) or not sample[k].strip()
                   for k in ("id", "raw_id", "context", "question")):
                raise ValueError("INVALID_INPUT_TEXT")
            if sample["id"] in self.samples:
                raise ValueError("DUPLICATE_INPUT_ID")
            self.samples[sample["id"]] = sample
        if manifest["ids"] != [{"id": s["id"], "raw_id": s["raw_id"]} for s in samples]:
            raise ValueError("PREPARATION_IDS_MISMATCH")
        if len(samples) != manifest["families"] or set(self.providers) != {s["raw_id"] for s in samples}:
            raise ValueError("PREPARATION_RECORDS_MISMATCH")
        self.sources = {s["name"]: s for s in manifest["sources"]}
        for source in self.sources.values():
            if file_hash(Path(source["path"])) != source["sha256"]:
                raise ValueError("ORIGINAL_SOURCE_HASH_MISMATCH")

    @traced("python")
    def case(self, case_id: str) -> dict:
        # [DP16] docs/02-architecture.md#DP16 — 없는 ID를 거절합니다. 무결성 오류는 DP14·DP15의 각 검사에서 거절합니다.
        # [BI04] docs/02-architecture.md#BI04 — 없는 ID 거절의 기존 번호이며 다른 무결성 오류는 DP14·DP15에 있습니다.
        if case_id not in self.samples:
            raise ValueError("UNKNOWN_INPUT_ID")
        # [BI03] docs/02-architecture.md#BI03 — 선택한 문제·private 원천·비교 정보를 깊은 복사로 반환합니다.
        sample = self.samples[case_id]
        provider = self.providers[sample["raw_id"]]
        comparison = {
            "id": case_id, "raw_id": sample["raw_id"],
            "source": self.sources[provider["source"]],
            "record_index": provider["record_index"], "question_id": provider["question_id"],
            "input_sha256": hashlib.sha256(json_bytes(sample)).hexdigest(),
            "raw_record_sha256": hashlib.sha256(json_bytes(provider)).hexdigest(),
            "input_fields": {k: sample[k] for k in ("context", "question", "reference_answer",
                                                     "reference_answer_type", "reference_precision")},
            "comparison_scope": "Source linkage and input snapshot; not a semantic audit.",
        }
        return copy.deepcopy({"sample": sample, "provider_record": provider,
                              "comparison": comparison, "input_path": str(self.path)})


@traced("python")
def load_case(input_path: Path, case_id: str | None = None) -> dict:
    if case_id is not None:
        return PreparedInputs(input_path).case(case_id)
    if (Path(input_path).parent / "preparation-start.json").exists():
        raise ValueError("INPUT_ID_REQUIRED")
    return _load_legacy_case(Path(input_path))


class RunContext:
    def __init__(self, output_dir: Path, handlers: Mapping[str, Handler | LLMHandler], case_id=None, *, seeded=False):
        self.root = output_dir.resolve()
        if seeded and not (self.root/'00-round-input/seed.json').is_file():
            raise ValueError('ROUND_SEED_REQUIRED')
        self.root.mkdir(parents=True, exist_ok=seeded)
        self.handlers = dict(handlers)
        self.trace = Journal(self.root, case_id)
        self.events = self.trace.events
        self.current_stage = "00-data-preparation"

    @classmethod
    def resume(cls, output_dir, handlers, case_id):
        """Continue stages without overwriting any existing stage artifact."""
        ctx=cls.__new__(cls);ctx.root=Path(output_dir).resolve()
        if not (ctx.root/'run.json').is_file():raise ValueError('EXISTING_CASE_REQUIRED')
        ctx.handlers=dict(handlers);ctx.trace=Journal.resume(ctx.root,case_id)
        ctx.events=ctx.trace.events;ctx.current_stage='pipeline'
        return ctx

    def save(self, relative: str, value):
        ordered_path = __import__('finarch.dataset.90-operations.ordered_artifacts', fromlist=['ordered_path']).ordered_path
        relative = ordered_path(relative)
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(json_bytes(value))
        self.trace.artifact(relative, value)
        if relative == "run.json" or relative.endswith("/03-result.json"):
            write_index = __import__('finarch.dataset.90-operations.numbered_layout', fromlist=['write_index']).write_index
            write_index(self.root)

    def save_text(self, relative: str, value: str):
        ordered_path = __import__('finarch.dataset.90-operations.ordered_artifacts', fromlist=['ordered_path']).ordered_path
        relative = ordered_path(relative)
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as stream:
            stream.write(value)
        self.trace.artifact(relative, value)
        if relative == "run.json" or relative.endswith("/03-result.json"):
            write_index = __import__('finarch.dataset.90-operations.numbered_layout', fromlist=['write_index']).write_index
            write_index(self.root)

    def invoke(self, stage: str, step: str, hook: str, payload: dict,
               local: Handler | LLMHandler | None = None) -> dict:
        # LG06: save START before even the request file; preserve failure/interrupt END.
        with self.trace.activate():
            function_name = {'01-preparation.03-calculation.pot':'01_generate_code','pot.execute':'03_execute_python'}.get(hook,hook)
            with self.trace.span(function_name, kind="llm" if hook in LLM_ROLES else "python",
                                 stage=stage, step=step, role=hook,
                                 axis=payload.get('axis'),
                                 candidate=stage.split("/")[-1] if "/" in stage else None):
                return self._invoke(stage, step, hook, payload, local)

    def _invoke(self, stage: str, step: str, hook: str, payload: dict,
                local: Handler | LLMHandler | None = None) -> dict:
        # [SC12] docs/02-architecture.md#SC12 — 단계 요청을 저장하고 고정 LLM 역할·허용 Python hook을 구분합니다.
        self.current_stage = stage
        self.save(f"{stage}/{step}/" + ("01-input/handler-input.json" if hook in LLM_ROLES else "01-input.json"), payload)
        handler = local if local is not None else self.handlers.get(hook)
        handler_invoked = False
        try:
            definition = None
            if hook in LLM_ROLES:
                definition = require_llm_schema(hook)
                # [SC13] docs/02-architecture.md#SC13 — 응답 정의를 저장하고 LLM handler에 keyword response_schema를 전달합니다.
                self.save(f"{stage}/{step}/01-input/handler-schema.json", definition)
            elif hook not in PYTHON_HOOKS:
                raise SchemaContractError("UNREGISTERED_STAGE_HOOK")
            # [SC14] docs/02-architecture.md#SC14 — 미연결은 NOT_IMPLEMENTED, 스키마·미등록 hook 오류는 아래 except에서 FAIL로 기록합니다.
            if handler is None:
                result = StepResult("NOT_IMPLEMENTED", f"Handler not connected: {hook}")
            elif definition is not None:
                # No fallback to a schema-free call if an adapter rejects this argument.
                handler_invoked = True
                result = handler(copy.deepcopy(payload), response_schema=copy.deepcopy(definition["schema"]))
            else:
                handler_invoked = True
                result = handler(copy.deepcopy(payload))
            if (not isinstance(result, StepResult) or result.status not in
                    ("PASS", "FAIL", "NOT_EVALUATED", "NOT_IMPLEMENTED")
                    or not isinstance(result.data, dict) or not isinstance(result.reason, str)):
                raise TypeError("INVALID_STEP_RESULT")
            json_bytes(asdict(result))
            if definition is not None:
                # [SC10] docs/02-architecture.md#SC10 — 유효한 LLM StepResult 원본을 보존하고 모든 LLM PASS 데이터를 재검사합니다.
                self.save(f"{stage}/{step}/03-result/handler-response.json", asdict(result))
                if result.status == "PASS":
                    try:
                        validate(hook + ".response", result.data)
                    except ValidationError as error:
                        errors = error.errors(include_input=False, include_url=False, include_context=False)
                        self.save(f"{stage}/{step}/03-result/handler-check.json", {"status": "FAIL", "errors": errors})
                        result = StepResult("FAIL", "RESPONSE_SCHEMA_INVALID", {"errors": errors})
                    else:
                        self.save(f"{stage}/{step}/03-result/handler-check.json", {"status": "PASS", "schema_sha256": definition["sha256"]})
        except SchemaContractError as error:
            self.save(f"{stage}/{step}/03-result/handler-check.json", {
                "status": "FAIL", "reason": error.reason, "schema_id": error.schema_id,
                "hook": hook, "phase": "after_call" if handler_invoked else "before_call",
                "handler_invoked": handler_invoked,
            })
            result = StepResult("FAIL", error.reason)
        except Exception as error:
            result = StepResult("FAIL", f"{type(error).__name__}: {error}")
        # [L01] docs/02-architecture.md#L01 — 결과를 저장하고 공통 로그의 종료 상태·산출물 경로를 연결합니다.
        self.save(f"{stage}/{step}/03-result.json", asdict(result))
        self.trace.update(status=result.status, reason=result.reason,
                          artifacts=[f"{stage}/{step}/01-input.json", f"{stage}/{step}/03-result.json"])
        # [SC11] docs/02-architecture.md#SC11 — PASS만 data를 반환하고 나머지는 StepStopped로 해당 경로를 중단합니다.
        if result.status != "PASS":
            raise StepStopped(stage, step, result)
        return result.data

    def check(self, stage: str, step: str, payload: dict, condition: bool, reason: str) -> dict:
        return self.invoke(stage, step, "python.check", payload,
                           local=lambda value: StepResult("PASS" if (condition() if callable(condition) else condition) else "FAIL", reason, value))


# [T02] docs/02-architecture.md#T02 — 원문·Unicode 위치·겹침·매핑을 검사하고 뒤쪽부터 patch를 적용합니다.
@traced("python")
def apply_patches(context: str, patches: list[dict]) -> str:
    """All offsets are Unicode character offsets into the unchanged original C."""
    if not isinstance(patches, list) or not patches:
        raise ValueError("PATCHES_REQUIRED")
    previous_end = -1
    previous_start = -1
    ordered = sorted(patches, key=lambda patch: (patch["start"], patch["end"]))
    for patch in ordered:
        start, end = patch["start"], patch["end"]
        if type(start) is not int or type(end) is not int or not 0 <= start <= end <= len(context):
            raise ValueError("INVALID_PATCH_OFFSETS")
        if start < previous_end or start == previous_start:
            raise ValueError("OVERLAPPING_OR_AMBIGUOUS_PATCHES")
        if (not isinstance(patch["text"], str) or patch["before"] != context[start:end]
                or not isinstance(patch["element_ids"], list) or not patch["element_ids"]
                or any(not isinstance(item, str) or not item for item in patch["element_ids"])):
            raise ValueError("INVALID_PATCH_OR_MAPPING")
        previous_start, previous_end = start, end
    changed = context
    for patch in reversed(ordered):
        changed = changed[:patch["start"]] + patch["text"] + changed[patch["end"]:]
    if changed == context:
        raise ValueError("NO_CONTEXT_CHANGE")
    return changed
