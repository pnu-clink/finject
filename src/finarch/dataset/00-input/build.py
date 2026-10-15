"""Freeze inputs from hash-verified local sources; do not infer generation success.

It never calls a model, runs source solution code, changes a raw file, or
overwrites an output folder. A terminal result distinguishes complete inputs
from partially written attempts and preserves counts and exclusions on failure.
"""

import hashlib
import json
from collections import Counter
from pathlib import Path

adapters = __import__('finarch.dataset.00-input.adapters', fromlist=['*'])
from finarch.shared.reference import load_raw
from finarch.dataset.schemas.registry import describe
from finarch.dataset.schemas.validation import validate


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value):
    if path.name == "input.json" and isinstance(value, list):
        value = [order_input_fields(sample) for sample in value]
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def order_input_fields(sample: dict) -> dict:
    """Present identity, question, context and answer before auxiliary content."""
    leading = ("id", "raw_id", "question", "context", "reference_answer",
               "reference_answer_type", "reference_precision", "answer_metadata")
    return {**{key: sample[key] for key in leading if key in sample},
            **{key: value for key, value in sample.items() if key not in leading}}


SOURCE_RATIO = {"finance-easy": 3, "finance-medium": 2, "finance-hard": 1, "tatqa-dev": 4}


def source_counts(total: int) -> dict[str, int]:
    """Keep the owner's exact 3:2:1:4 ratio without implicit rounding."""
    if type(total) is not int or total < 10 or total % 10:
        raise ValueError("TOTAL_MUST_BE_A_POSITIVE_MULTIPLE_OF_TEN")
    return {name: weight * (total // 10) for name, weight in SOURCE_RATIO.items()}


def prepare(catalog_path: Path, output: Path, per_source: int | None = None,
            seed: str = "finarch", *, total: int | None = None, source_quotas: dict | None = None) -> dict:
    # [DP03] docs/02-architecture.md#DP03 — 개수 검증 후 새 출력 폴더와 시작 기록을 만듭니다.
    # [I00] docs/02-architecture.md#I00 — 준비 전체를 가리키던 기존 요약 번호입니다. 상세는 DP03–DP12입니다.
    catalog_path, output = Path(catalog_path), Path(output)
    if source_quotas is not None:
        if total is not None or per_source is not None:raise ValueError("CHOOSE_SOURCE_QUOTAS_OR_COUNTS")
        if not source_quotas or any(type(v) is not int or v<1 for v in source_quotas.values()):raise ValueError("INVALID_SOURCE_QUOTAS")
    if total is not None and per_source is not None:
        raise ValueError("CHOOSE_TOTAL_OR_PER_SOURCE")
    if total is not None:
        source_counts(total)
    elif source_quotas is None and (type(per_source) is not int or per_source < 1):
        raise ValueError("PER_SOURCE_MUST_BE_POSITIVE")
    output.mkdir(parents=True, exist_ok=False)
    progress = {"stage": "catalog", "source": None, "record_index": None,
                "question_id": None, "counts": Counter(), "exclusions": [], "sources": []}
    write_json(output / "preparation-start.json", {
        "format": "fin-arch-preparation-attempt-v1", "status": "RUNNING", "model_calls": 0,
        "catalog_path": str(catalog_path.resolve()), "per_source": per_source,
        "total": total, "seed": seed})
    try:
        result = _prepare(catalog_path, output, per_source, seed, progress, total, source_quotas)
        # [DP11] docs/02-architecture.md#DP11 — manifest 해시를 담은 완료 PASS를 마지막에 저장합니다.
        progress.update(stage="complete", source=None, record_index=None, question_id=None)
        write_json(output / "preparation-result.json", {
            "format": "fin-arch-preparation-attempt-v1", "status": "PASS", **result,
            "manifest_sha256": sha256((output / "selection-manifest.json").read_bytes()),
            "counts": dict(progress["counts"]), "exclusions": progress["exclusions"]})
        return result
    # [DP12] docs/02-architecture.md#DP12 — 진행 위치·집계·제외 이유를 FAIL로 저장하고 원래 오류를 전달합니다.
    except Exception as error:
        failure = {"format": "fin-arch-preparation-attempt-v1", "status": "FAIL",
                   "model_calls": 0, "error_type": type(error).__name__, "reason": str(error),
                   **progress}
        try:
            write_json(output / "preparation-result.json", failure)
        except OSError as save_error:
            error.add_note(f"Could not save preparation failure: {save_error}")
        raise


def _prepare(catalog_path: Path, output: Path, per_source: int | None, seed: str,
             progress: dict, total: int | None, source_quotas=None) -> dict:
    # [DP04] docs/02-architecture.md#DP04 — 출처 목록·할당량을 확인하고 출처별 원천 해시를 검사합니다.
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    names = [spec["name"] for spec in catalog["sources"]]
    if len(names) != len(set(names)):
        raise ValueError("DUPLICATE_SOURCE_NAME")
    quotas = source_quotas if source_quotas is not None else source_counts(total) if total is not None else dict.fromkeys(names, per_source)
    if set(quotas) != set(names):
        raise ValueError("RATIO_REQUIRES_EASY_MEDIUM_HARD_AND_TATQA")
    selected, counts, exclusions = [], progress["counts"], progress["exclusions"]
    source_summaries = progress["sources"]
    raw_ids = set()
    for spec in catalog["sources"]:
        progress.update(stage="source_integrity", source=spec["name"], record_index=None,
                        question_id=None)
        source_path = Path(spec["path"])
        if not source_path.is_absolute():
            source_path = catalog_path.parent / source_path
        content = source_path.read_bytes()
        if sha256(content) != spec["sha256"]:
            raise ValueError("SOURCE_HASH_MISMATCH: " + spec["name"])
        if spec["adapter"] not in ("finance", "tatqa"):
            raise ValueError("UNKNOWN_SOURCE_ADAPTER")
        provenance = {"name": spec["name"], "sha256": spec["sha256"],
                      "url": spec["url"], "commit": spec["commit"]}
        source_summaries.append({**provenance, "path": str(source_path.resolve())})
        pool = []
        # [DP05] docs/02-architecture.md#DP05 — 질문별 후보를 추출하고 검토 수·제외 이유를 보존합니다.
        for record_index, record in enumerate(load_raw(content)):
            progress.update(stage="extract", record_index=record_index, question_id=None)
            questions = [None] if spec["adapter"] == "finance" else record["questions"]
            for question in questions:
                progress["question_id"] = (question.get("uid") if question is not None
                                           else record.get("question_id"))
                counts[spec["name"] + ":examined"] += 1
                try:
                    sample = (adapters.finance(record, provenance) if question is None
                              else adapters.tatqa(record, question, provenance))
                except ValueError as error:
                    exclusions.append({"source": spec["name"], "record_index": record_index,
                                       "question_id": question.get("uid") if question else record.get("question_id"),
                                       "reason": str(error)})
                    continue
                if not isinstance(sample["context"], str) or not sample["context"].strip():
                    raise ValueError("INVALID_CONTEXT")
                if not isinstance(sample["question"], str) or not sample["question"].strip():
                    raise ValueError("INVALID_QUESTION")
                if sample["raw_id"] in raw_ids:
                    raise ValueError("DUPLICATE_RAW_ID: " + sample["raw_id"])
                raw_ids.add(sample["raw_id"])
                pool.append((sample, {"source": spec["name"], "record_index": record_index,
                                      "record": record, "question_id": question["uid"] if question else None}))
        progress.update(stage="select", record_index=None, question_id=None)
        # [DP08] docs/02-architecture.md#DP08 — seed 순위를 정하고 출처 안에서 동일 본문을 한 번만 선택합니다.
        pool.sort(key=lambda pair: sha256((seed + ":" + pair[0]["raw_id"]).encode()))
        group, seen = [], set()
        for pair in pool:
            signature = sha256(pair[0]["context"].encode())
            if signature in seen:
                exclusions.append({"source": spec["name"], "raw_id": pair[0]["raw_id"],
                                   "reason": "DUPLICATE_CONTEXT"})
                continue
            seen.add(signature)
            group.append(pair)
        counts[spec["name"] + ":eligible_unique_contexts"] = len(group)
        requested = quotas[spec["name"]]
        counts[spec["name"] + ":requested"] = requested
        # [DP09] docs/02-architecture.md#DP09 — 후보 부족은 오류, 충분하면 해당 출처 할당량만 선택합니다.
        if len(group) < requested:
            raise ValueError("INSUFFICIENT_ELIGIBLE_INPUTS: " + spec["name"])
        selected.extend(group[:requested])
        counts[spec["name"] + ":selected"] = requested
        counts[spec["name"] + ":not_selected_by_rank"] = len(group) - requested
    if not selected:
        raise ValueError("NO_INPUTS")
    selected.sort(key=lambda pair: sha256((seed + ":order:" + pair[0]["raw_id"]).encode()))
    samples = [{"id": f"test-{i:04d}", **pair[0]} for i, pair in enumerate(selected, 1)]
    providers = {pair[0]["raw_id"]: pair[1] for pair in selected}
    progress.update(stage="write_bundle", source=None, record_index=None, question_id=None)
    # [DP10] docs/02-architecture.md#DP10 — 준비 스키마 검사 후 input·provider-records·manifest를 저장합니다.
    validate("01-preparation.01-source.prepared-input", samples)
    write_json(output / "input.json", samples)
    write_json(output / "provider-records.json", providers)
    manifest = {"format": "fin-arch-preparation-v1", "families": len(samples), "model_calls": 0,
                "input_schema": {k: v for k, v in describe("01-preparation.01-source.prepared-input").items() if k != "schema"},
                "selection_seed": seed, "per_source": per_source, "counts": dict(counts),
                "requested_total": total, "source_counts": quotas,
                "selection_policy": {"question_unit": "one question per sample",
                                     "context_deduplication": "one sample per context within source; confirmed by owner",
                                     "finance_scope": "FinanceReasoning-native only; existing adapter scope"},
                "exclusions": exclusions, "sources": source_summaries,
                "provider_file_sha256": sha256((output / "provider-records.json").read_bytes()),
                "input_file_sha256": sha256((output / "input.json").read_bytes()),
                "ids": [{"id": s["id"], "raw_id": s["raw_id"]} for s in samples],
                "purpose": "development input, not a held-out evaluation",
                "limitations": ["Adapter compatibility is not semantic correctness.",
                                "Source records are private provenance, not model payloads.",
                                "Input count does not prescribe generation axes or accepted record count."]}
    write_json(output / "selection-manifest.json", manifest)
    return {"output": str(output), "families": len(samples), "model_calls": 0}


def prepare_explicit_finance(raw_manifest, output, *, source_name, indices):
    """Explicit user-selected source records; reuse adapter/schema/hash contract."""
    raw_manifest, output = Path(raw_manifest), Path(output)
    output.mkdir(parents=True, exist_ok=False)
    meta = next(x for x in json.loads(raw_manifest.read_text())['files'] if x['name']==source_name)
    path=raw_manifest.parent/meta['file'];content=path.read_bytes()
    if sha256(content)!=meta['sha256']:raise ValueError('SOURCE_HASH_MISMATCH')
    source={'name':source_name,'sha256':meta['sha256'],'url':meta['upstream_url'],'commit':meta['upstream_commit']}
    records=load_raw(content);samples=[];providers={}
    for number,index in enumerate(indices,1):
        record=records[index];sample=adapters.finance(record,source,allow_embedded=True)
        samples.append({'id':f'test-{number:04d}',**sample})
        providers[sample['raw_id']]={'source':source_name,'record_index':index,'record':record,'question_id':record['question_id']}
    validate('01-preparation.01-source.prepared-input',samples)
    write_json(output/'input.json',samples);write_json(output/'provider-records.json',providers)
    manifest={'families':len(samples),'sources':[{**source,'path':str(path.resolve())}],
              'input_schema':{k:v for k,v in describe('01-preparation.01-source.prepared-input').items() if k!='schema'},
              'input_file_sha256':sha256((output/'input.json').read_bytes()),'provider_file_sha256':sha256((output/'provider-records.json').read_bytes()),
              'ids':[{'id':s['id'],'raw_id':s['raw_id']} for s in samples],
              'selection_policy':'Explicit user indices, not random native-only sampling','selected_indices':indices}
    write_json(output/'selection-manifest.json',manifest)
    write_json(output/'preparation-result.json',{'status':'PASS','manifest_sha256':sha256((output/'selection-manifest.json').read_bytes()),'model_calls':0})
    (output/'README.md').write_text('Explicit source selection. Read selection-manifest.json, input.json, provider-records.json. Original source and gold preserved; not sent to the author.\n')
    return output/'input.json'


def prepare_cohort_finance(raw_manifest, output, selections, *, per_cohort=15):
    """Build a balanced private selection using the existing source adapter contract.

    Cohort expectations stay in the selection manifest, never in model inputs.
    """
    raw_manifest, output = Path(raw_manifest), Path(output)
    if type(per_cohort) is not int or per_cohort < 1 or len(selections)!=2*per_cohort or any(sum(x['cohort']==c for x in selections)!=per_cohort for c in ('INTERNAL','EXTERNAL')):
        raise ValueError('EXPECTED_BALANCED_COHORT_SELECTION')
    if len({(x['source'],x['index'],x.get('question_id')) for x in selections})!=len(selections):
        raise ValueError('DUPLICATE_SELECTION')
    metadata={x['name']:x for x in json.loads(raw_manifest.read_text())['files']}
    sources={};records={};samples=[];providers={};selection=[]
    for number,item in enumerate(selections,1):
        name=item['source']
        if name not in records:
            meta=metadata[name];path=raw_manifest.parent/meta['file'];content=path.read_bytes()
            if sha256(content)!=meta['sha256']:raise ValueError('SOURCE_HASH_MISMATCH')
            sources[name]={'name':name,'sha256':meta['sha256'],'url':meta['upstream_url'],
                           'commit':meta['upstream_commit'],'path':str(path.resolve())}
            records[name]=load_raw(content)
        record=records[name][item['index']]
        provenance={k:v for k,v in sources[name].items() if k!='path'}
        if name=='tatqa-dev':
            question=next(q for q in record['questions'] if q['uid']==item['question_id'])
            sample=adapters.tatqa(record,question,provenance)
            question_id=question['uid']
        else:
            sample=adapters.finance(record,provenance,allow_embedded=False)
            question_id=record['question_id']
        sample={'id':f'test-{number:04d}',**sample};samples.append(sample)
        providers[sample['raw_id']]={'source':name,'record_index':item['index'],'record':record,'question_id':question_id}
        selection.append({'id':sample['id'],'raw_id':sample['raw_id'],**item})
    validate('01-preparation.01-source.prepared-input',samples)
    output.mkdir(parents=True,exist_ok=False)
    write_json(output/'input.json',samples);write_json(output/'provider-records.json',providers)
    manifest={'families':len(selections),'sources':list(sources.values()),'selection':selection,
              'input_schema':{k:v for k,v in describe('01-preparation.01-source.prepared-input').items() if k!='schema'},
              'input_file_sha256':sha256((output/'input.json').read_bytes()),
              'provider_file_sha256':sha256((output/'provider-records.json').read_bytes()),
              'ids':[{'id':s['id'],'raw_id':s['raw_id']} for s in samples],
              'selection_policy':f'Preliminary Q/C-based development selection: {per_cohort} internal-context and {per_cohort} external-context expectations; not representative sampling.',
              'cohort_counts':{'INTERNAL':per_cohort,'EXTERNAL':per_cohort},
              'limitations':['Preliminary expectations are not verification verdicts.',
                             'External cases exercise missing financial rules, not live table retrieval.',
                             'Selection labels and original solutions are not author inputs.']}
    write_json(output/'selection-manifest.json',manifest)
    write_json(output/'preparation-result.json',{'status':'PASS','manifest_sha256':sha256((output/'selection-manifest.json').read_bytes()),'model_calls':0})
    (output/'README.md').write_text(Path(__file__).with_name('cohort-readme.md').read_text().replace('{total}',str(len(selections))).replace('{per_cohort}',str(per_cohort)))
    return output/'input.json'
