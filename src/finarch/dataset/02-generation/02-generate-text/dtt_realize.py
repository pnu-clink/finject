resolve_read = __import__('finarch.dataset.90-operations.ordered_artifacts', fromlist=['resolve_read']).resolve_read
candidate_root = __import__('finarch.dataset.90-operations.stage_paths', fromlist=['candidate_root']).candidate_root
generation_root = __import__('finarch.dataset.90-operations.stage_paths', fromlist=['generation_root']).generation_root
variant_root = __import__('finarch.dataset.90-operations.stage_paths', fromlist=['variant_root']).variant_root
"""R16: realize saved, checked plans; stop before stage17 semantic auditing.

CLI invocation: PYTHONPATH=src python -m finarch.dataset.02-generation.02-generate-text.dtt_realize --case ...
--config ... . All outputs are exclusive writes; no retries or semantic promotion.
"""
import argparse
from collections import Counter
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re

RunContext = __import__('finarch.dataset.90-operations.staging', fromlist=['RunContext']).RunContext
StepResult = __import__('finarch.dataset.90-operations.staging', fromlist=['StepResult']).StepResult
StepStopped = __import__('finarch.dataset.90-operations.staging', fromlist=['StepStopped']).StepStopped
apply_patches = __import__('finarch.dataset.90-operations.staging', fromlist=['apply_patches']).apply_patches
from finarch.shared.providers.cli import call, read_settings
from finarch.dataset.shared.calculation.python_graph import load_graph
check_base = __import__('finarch.dataset.02-generation.01-perturbation.source_plan', fromlist=['check_base']).check_base
compose_pair = __import__('finarch.dataset.02-generation.01-perturbation.value_positions', fromlist=['compose_pair']).compose_pair
from finarch.dataset.schemas.registry import describe
from finarch.dataset.schemas.validation import validate


def read(path):
    resolve_read = __import__('finarch.dataset.90-operations.ordered_artifacts', fromlist=['resolve_read']).resolve_read
    return json.loads(resolve_read(path).read_text())


def digest(path):
    resolve_read = __import__('finarch.dataset.90-operations.ordered_artifacts', fromlist=['resolve_read']).resolve_read
    return hashlib.sha256(resolve_read(path).read_bytes()).hexdigest()


def numbers(text):
    return Counter(Decimal(x.replace(',', '')) for x in
                   re.findall(r'(?<![\w.])-?\d+(?:,\d{3})*(?:\.\d+)?(?!\w|[.,]\d)', text))


def slot(start, end, before, ids, kind, instruction, exact=None, prefix='', allowed=()):
    return dict(start=start, end=end, before=before, element_ids=ids, text='',
                kind=kind, instruction=instruction, exact_text=exact,
                required_prefix=prefix, allowed_numbers=list(allowed))


def checked_plan(case, variant):
    """R16.1: qualify the saved calculation plan, not its unrun semantic audit."""
    plan = variant['plan']; axis = variant['axis']
    if plan.get('axis') != axis or variant.get('status') == 'FAIL':
        raise ValueError('PLAN_AXIS_OR_STATUS_INVALID')
    base = plan
    if 'base_plan_ref' in plan:
        path = (case / plan['base_plan_ref']).resolve()
        if not path.is_relative_to(case.resolve()) or digest(path) != plan['base_plan_sha256']:
            raise ValueError('BASE_PLAN_CHANGED')
        base = read(path)
    for path, expected in plan.get('preserved_inputs_sha256', {}).items():
        if digest(case/path) != expected:
            raise ValueError('PRESERVED_INPUT_CHANGED')
    if axis in ('IC_VALUE', 'IC_SOURCE'):
        check_base(base)
        if digest(case/'03-graph/04-save-graph/01-graph.json') != base['original_graph_sha256']:
            raise ValueError('ORIGINAL_GRAPH_CHANGED')
    elif axis == 'IC_RELATION':
        if (plan.get('method') not in ('explicit-positive-ratio-v1', 'scoped-operation-v1')
                or set(plan['branches']) != {'B'}
                or not plan['checks'] or not all(v is True for v in plan['checks'].values())):
            raise ValueError('RELATION_PLAN_NOT_CHECKED')
    elif axis == 'EA':
        review = read(case/f"{variant_root(variant['label'])}/04-deletion-check.json")
        if (review.get('status') != 'PASS' or plan.get('calculation_status') != 'MISSING_EVIDENCE'
                or not plan['checks'] or not all(v is True for v in plan['checks'].values())):
            raise ValueError('EA_PLAN_NOT_CHECKED')
    else:
        raise ValueError('UNSUPPORTED_REALIZATION_AXIS')
    return base


def make_request(case, variant, sample, program, graph, value_sentence=None):
    """Project explicit editing inputs; omit gold, audit results and computed answers."""
    plan = variant['plan']; axis = variant['axis']; base = checked_plan(case, variant)
    preview = read(case/f"{variant_root(variant['label'])}/05-text-input-preview.json")
    context = sample['context']
    if preview['original_context'] != context or preview['question'] != sample['question']:
        raise ValueError('PREVIEW_ORIGINAL_CHANGED')
    nodes = [{k: n[k] for k in ('id', 'kind', 'label', 'inputs', 'operator', 'fact_id', 'code_line') if k in n}
             for n in graph['nodes']]
    if (case/'04-perturbation/00-receive-input/01-input.json').exists():
        realization_request = __import__('finarch.dataset.02-generation.01-perturbation.production_plan', fromlist=['realization_request']).realization_request
        return realization_request(case, variant, sample, program, graph, base, preview, value_sentence)
    raise ValueError('LEGACY_PREWRITTEN_REQUEST_DISABLED: structured generation spec required')


def check_response(request, response):
    """R16.3: typed response, exact authorized ranges/IDs, numeric constraints, then apply."""
    validate('02-generation.02-generate-text.realization.response', response)
    patches = sorted(response['patches'], key=lambda p: (p['start'], p['end']))
    slots = sorted(request['edit_slots'], key=lambda p: (p['start'], p['end']))
    if len(patches) != len(slots):
        raise ValueError('EDIT_SLOT_COUNT_MISMATCH')
    enriched = []
    for patch, spec in zip(patches, slots):
        if any(patch[k] != spec[k] for k in ('start', 'end', 'before', 'element_ids')):
            raise ValueError('UNAUTHORIZED_PATCH_OR_GRAPH_MAPPING')
        text = patch['text']
        if spec['exact_text'] is not None and text != spec['exact_text']:
            raise ValueError('FIXED_TEXT_OR_MINIMAL_DELETION_CHANGED')
        if not text.startswith(spec['required_prefix']):
            raise ValueError('RELATION_PARAGRAPH_SEPARATOR_REQUIRED' if spec['kind']=='RELATION' else 'FIXED_VALUE_SENTENCE_CHANGED')
        if spec['kind'].startswith('SOURCE_') and 'one parenthesized source attribution' in spec['instruction']:
            if not re.fullmatch(r' \([^()\n]+\)', text):
                raise ValueError('PARENTHESIZED_SOURCE_REQUIRED')
        if (spec['kind']=='VALUE' and request['axis']=='IC_VALUE') or spec['kind']=='RELATION':
            c=request['context']; position=spec['start']
            placement_error='RELATION_INSIDE_TABLE' if spec['kind']=='RELATION' else 'VALUE_INSIDE_TABLE'
            line_start=c.rfind('\n',0,position)+1
            line_end=c.find('\n',position)
            if line_end<0:line_end=len(c)
            if '|' in c[line_start:line_end]:
                if position not in (line_start,line_end):raise ValueError(placement_error)
                previous=c[c.rfind('\n',0,max(0,line_start-1))+1:max(0,line_start-1)]
                next_end=c.find('\n',line_end+1)
                following=c[line_end+1:next_end if next_end>=0 else len(c)]
                if position==line_start and '|' in previous:raise ValueError(placement_error)
                if position==line_end and '|' in following:raise ValueError(placement_error)
                if spec['kind']=='RELATION':
                    if position!=line_end:raise ValueError('RELATION_AFTER_TABLE_REQUIRED')
                    if not text.startswith('\n\n') or (position<len(c) and not text.endswith('\n')):
                        raise ValueError('RELATION_PARAGRAPH_SEPARATOR_REQUIRED')
        actual=numbers(text);required=Counter(Decimal(n) for n in spec['allowed_numbers'])
        if spec['kind']=='EA':
            valid=actual==required
        elif spec['kind']=='RELATION':
            scoped = 'Use only the numbers in allowed_numbers.' in spec['instruction']
            permitted=set(required) if scoped else set(numbers(request['context']))|set(required)|{n*100 for n in required}
            valid=set(actual)<=permitted
        else:
            permitted=set(numbers(request['context']))|set(required)
            valid=not (required-actual) and set(actual)<=permitted
        if not valid:raise ValueError('UNPLANNED_NUMERIC_CONTENT')
        if re.search(r'EA_DELETE|IC[_-](?:VALUE|SOURCE|RELATION)|\[.*?\]', text, re.I):
            raise ValueError('CONSTRUCTION_TAG_IN_CONTEXT')
        if re.search(r'\b\w+_\w+\b', text):
            raise ValueError('PYTHON_IDENTIFIER_IN_CONTEXT')
        if not text.strip() and spec['kind'] != 'EA':
            raise ValueError('EMPTY_PERTURBATION')
        if spec['kind'] == 'VALUE' and request['axis'] == 'IC_VALUE':
            if re.search(r'\b(?:that same|this figure|above-mentioned)\b', text, re.I):
                raise ValueError('POSITION_DEPENDENT_SENTENCE')
            if not text.strip().endswith('.') or '\n' in text.strip():
                raise ValueError('STANDALONE_SENTENCE_REQUIRED')
        if spec['start'] == spec['end'] and text:
            c = request['context']; start = spec['start']
            if (start and not c[start-1].isspace() and text[0].isalnum()) or (
                    start < len(c) and c[start].isalnum() and not text[-1].isspace()):
                raise ValueError('INSERTION_NEEDS_SEPARATOR')
        segments = [{'kind': spec['kind'], 'text': text}]
        if spec['kind'] == 'SOURCE_B' and spec['required_prefix']:
            n = len(spec['required_prefix']) - len(', according to ')
            segments = [{'kind': 'VALUE', 'text': text[:n]}, {'kind': 'SOURCE_B', 'text': text[n:]}]
        enriched.append({**patch, 'segments': segments, 'purpose': spec['instruction']})
    context = apply_patches(request['context'], patches)
    return {'context': context, 'question': request['question']}, enriched


README_TEMPLATE = """# 16번 실제 문장 생성 — {label}

상태: {status}. 의미 판정·독립 풀이(17·18번)는 미실행, 역산은 보류입니다.

읽는 순서:
1. `01-input.json`: 전달할 원문·편집 범위·Python/DAG 연결.
2. {call_note}
3. `03-result/validation.json`: 위치·원문·겹침·그래프 ID·보존 및 숫자 검사.
4. `03-result/patches.json` → `04-final-observation.json`: 실제 적용 내역 → 본문·질문만.
5. `03-result.json`, `03-result/metadata.json`: 뷰어 비교 및 앞/뒤 위치·출처 조건·호출 연결.

뷰어: http://127.0.0.1:8893/?run={run}&case={case}&tab=dtt
해당 유형의 5번 문장과 답변에서 실제 본문과 하단 LLM 디버그를 확인합니다.
`events.jsonl`과 `usage.jsonl`은 문항 루트의 공통 로그입니다.
"""


def finish(ctx, variant, request, response, call_ref, pair_preview=None, stage=None):
    label = variant['label']; stage = stage or generation_root(label)+'/attempt-001'
    with ctx.trace.activate(), ctx.trace.span('dtt.patch_and_save', stage=stage, step='06-apply-result', role='python'):
        final, patches = check_response(request, response)
        preview = deepcopy(pair_preview or read(ctx.root/f'{variant_root(label)}/05-text-input-preview.json'))
        preview['axis'] = variant['axis']
        if variant['axis']=='IC_SOURCE':
            preview['original_context']=request['context']
            base_variant = __import__('finarch.dataset.02-generation.01-perturbation.source_from_value', fromlist=['base_variant']).base_variant
            preview['source_base_label']=base_variant(variant)
            preview['source_condition']=variant['plan']['source_condition']
            preview['claim_order']=variant['plan']['claim_order']
            preview['question']=request['question']
        if preview['axis'] == 'EA':
            patch = patches[0]
            preview['rewritten_sentence'] = {'start':patch['start'], 'end':patch['start']+len(patch['text']), 'text':patch['text']}
        preview.update(status='GENERATED', origin='LLM response validated and applied by Python',
                       final_text_status='GENERATED', semantic_status='NOT_EVALUATED',
                       preview_context=final['context'], patches=patches, model_calls=0 if call_ref!=stage+'/realize' else 1,
                       realization_call_ref=call_ref, next_steps=['Audit the final text semantics', 'Human review'])
        metadata = {k: preview[k] for k in ('axis', 'source_base_label', 'pair_id', 'perturb_position', 'claim_order',
                    'source_condition', 'target_sentence', 'perturb_sentence') if k in preview}
        metadata.update(stage16_status='PASS', semantic_status='NOT_EVALUATED', independent_answer_status='NOT_RUN',
                        recovery_review='SKIPPED_BY_USER', realization_call_ref=call_ref,
                        plan_sha256=hashlib.sha256(json.dumps(variant['plan'], sort_keys=True).encode()).hexdigest())
        ctx.save(stage+'/03-result/validation.json', {'status':'PASS', 'checks': ['response_schema', 'authorized_ranges',
                 'before_matches', 'no_overlap', 'graph_ids', 'numeric_contract', 'question_preserved'],
                 'semantic_status':'NOT_EVALUATED', 'ea_scope':'authorized sentence or table cell' if variant['axis']=='EA' else None})
        ctx.save(stage+'/03-result/patches.json', patches)
        ctx.save(stage+'/03-result.json', preview)
        ctx.save(stage+'/03-result/metadata.json', metadata)
        ctx.save(stage+'/04-final-observation.json', final)
        ctx.save_text(stage+'/context.txt', final['context'])
        ctx.save_text(stage+'/README.md', README_TEMPLATE.format(label=label, status='PASS', run=(ctx.root.parent.parent.name+'&round='+ctx.root.parent.name if ctx.root.parent.name.endswith('-round') else ctx.root.parent.name),
            case=ctx.root.name, call_note=f'실제 호출 기록: `{call_ref}/` (입력·프롬프트·스키마·원응답·토큰).'))
        ctx.trace.update(status='PASS', reason='Stage16 structural editing passed; semantic audit not run.')
        return preview


def run(case_dir, config_path, revision=None, selected_labels=None):
    case = Path(case_dir).resolve(); graph, program = None, read(case/'02-calculation/02-prepare-code/03-program.json')
    graph = load_graph(case)
    sample = read(case/'00-data-preparation/01-select-input/01-input.json'); variants = read(case/'04-perturbation/05-list-candidates/03-result.json')
    if revision is not None and (not re.fullmatch(r'[a-zA-Z0-9_-]+',revision)):
        raise ValueError('INVALID_REVISION')
    if selected_labels:
        if set(selected_labels)-{v['label'] for v in variants}:
            raise ValueError('UNKNOWN_VARIANT_LABEL')
        variants=[v for v in variants if v['label'] in selected_labels]
    def stage_for(label):
        return generation_root(label)+'/'+(revision or 'attempt-001')
    labels = [v['label'] for v in variants]
    if len(labels) != len(set(labels)):
        raise ValueError('DUPLICATE_VARIANT_LABEL')
    # R16.0: check all active plans and protected inputs before any paid call.
    for v in variants:
        if Path(v['label']).name != v['label'] or v['label'] in ('.','..'):
            raise ValueError('INVALID_VARIANT_LABEL')
        checked_plan(case, v)
        if (case/stage_for(v['label'])).exists():
            raise ValueError('STAGE16_ALREADY_HAS_OUTPUTS: '+v['label'])
    settings = read_settings(config_path, '02-generation.02-generate-text.realization')
    ctx = RunContext.resume(case, {}, case.name); family='05-text/01-generate-text/00-run-summary/'+(revision or 'attempt-001')
    ctx.save(family+'/config.json', read(config_path))
    ctx.save(family+'/plan.json', {'labels':labels, 'model':settings['model'], 'effort':settings['effort'],
             'maximum_cli_invocations':len(variants)-sum(v.get('perturb_position')=='after' for v in variants),
             'automatic_retries':0, 'estimated_cost':None, 'cost_status':'CLI billing price unavailable',
             'stop_after':'16', 'semantic_status':'NOT_EVALUATED'})
    original_hashes={p:digest(case/p) for p in ('02-calculation/02-prepare-code/03-program.json','00-data-preparation/01-select-input/01-input.json','03-graph/04-save-graph/01-graph.json','04-perturbation/05-list-candidates/03-result.json')}
    results=[]; pairs={}; generated_sentence=None; prerequisite_audit={}
    for variant in variants:
        label=variant['label']; stage=stage_for(label)
        try:
            if variant.get('perturb_position') == 'after':
                prior=pairs.get(variant['pair_id'])
                if prior is None:
                    raise ValueError('PAIR_SOURCE_GENERATION_FAILED')
                before_preview, call_ref=prior
                payload=read(case/f'{variant_root(label)}/06-generation-input.json')
                pair=compose_pair(payload, before_preview['perturb_sentence'], variant['pair_id'])
                other=pair[1]
                request=make_request(case,variant,sample,program,graph)
                ctx.save(stage+'/01-input.json',request)
                response={'patches':[{k:p[k] for k in ('start','end','before','text','element_ids')} for p in other['patches']]}
                ctx.save(stage+'/02-pair-placement.json', {'source_call_ref':call_ref,'response':response,'model_calls':0})
                finish(ctx,variant,request,response,call_ref,other,stage=stage)
            else:
                if variant['axis']=='IC_SOURCE':
                    base_variant = __import__('finarch.dataset.02-generation.01-perturbation.source_from_value', fromlist=['base_variant']).base_variant
                    base_label=base_variant(variant)
                    if base_label not in prerequisite_audit:
                        from finarch.dataset.shared.review.dtt_audit import prepare, audit_one, publish
                        audit_root = __import__('finarch.dataset.90-operations.stage_paths', fromlist=['audit_root']).audit_root
                        value_base = __import__('finarch.dataset.02-generation.01-perturbation.source_from_value', fromlist=['value_base']).value_base
                        try:
                            _,_,_,base_binding=value_base(case,base_label)
                            prerequisite_audit[base_label]=read(case/base_binding['audit_ref']/'03-result.json')
                        except (FileNotFoundError, ValueError, KeyError):
                            audit_request,binding=prepare(case,base_label)
                            audit_stage=audit_root(base_label)+'/'+(revision or 'attempt-001')
                            prerequisite_audit[base_label]=audit_one(ctx,config_path,audit_request,binding,audit_stage,base_label)
                            publish(ctx,base_label,audit_stage,prerequisite_audit[base_label])
                request=make_request(case,variant,sample,program,graph,generated_sentence)
                if variant['axis']=='IC_SOURCE':
                    value_base = __import__('finarch.dataset.02-generation.01-perturbation.source_from_value', fromlist=['value_base']).value_base
                    ctx.save(stage+'/01-input/source-binding.json',value_base(case,base_variant(variant))[3])
                ctx.save(stage+'/01-input.json',request)
                call_ref=stage+'/realize'
                def handler(payload, *, response_schema):
                    if response_schema != describe('02-generation.02-generate-text.realization.response')['schema']:
                        raise ValueError('RESPONSE_SCHEMA_CHANGED')
                    return call(config_path,'02-generation.02-generate-text.realization',payload,save=lambda name,value:ctx.save(call_ref+'/'+name,value))
                response=ctx.invoke(stage,'03-LLM-call','02-generation.02-generate-text.realization',request,local=handler)
                if variant['axis']=='IC_VALUE' and variant.get('pair_id'):
                    check_response(request,response)
                    generated_sentence=response['patches'][0]['text'].strip()
                    payload=read(case/f'{variant_root(label)}/06-generation-input.json')
                    pair=compose_pair(payload,generated_sentence,variant['pair_id'])
                    preview=finish(ctx,variant,request,response,call_ref,pair[0],stage=stage)
                    pairs[variant['pair_id']]=(preview,call_ref)
                else:
                    finish(ctx,variant,request,response,call_ref,stage=stage)
            if revision:
                # Publish a successful revision only. Earlier raw responses/artifacts remain intact.
                pointer=case/candidate_root(label)/'latest-realization.json'
                if pointer.exists():
                    ctx.save(stage+'/previous-latest-realization.json',read(pointer))
                    temporary=pointer.with_suffix('.tmp')
                    with temporary.open('x') as stream:
                        json.dump({'stage':stage,'revision':revision},stream,ensure_ascii=False)
                    temporary.replace(pointer)
                    ctx.trace.artifact(str(pointer.relative_to(case)))
                else:
                    ctx.save(candidate_root(label)+'/latest-realization.json',{'stage':stage,'revision':revision})
            results.append({'label':label,'status':'PASS','semantic_status':'NOT_EVALUATED'})
        except (StepStopped, ValueError, KeyError, TypeError) as error:
            reason=error.result.reason if isinstance(error,StepStopped) else str(error)
            ctx.save(stage+'/03-result/failure.json',{'status':'FAIL','reason':reason,'automatic_retry':False})
            ctx.save_text(stage+'/README.md',f'# 16번 {label}\n\n실패: {reason}\n원요청·수신 원응답·검사 기록을 보존했습니다. 최종 본문은 다음 단계로 넘기지 않습니다.\n')
            results.append({'label':label,'status':'FAIL','reason':reason})
        print(json.dumps(results[-1],ensure_ascii=False),flush=True)
    preserved=all(digest(case/p)==h for p,h in original_hashes.items())
    usage=[read(case/stage_for(v['label'])/'realize/03-result/usage.json') for v in variants
           if resolve_read(case/stage_for(v['label'])/'realize/03-result/usage.json').exists()]
    summary={'status':'PASS' if preserved and all(r['status']=='PASS' for r in results) else 'FAIL',
             'results':results,'original_inputs_unchanged':preserved,'original_sha256':original_hashes,
             'cli_invocations':sum(u['cli_invocations'] for u in usage),
             'usage':[{'label':v['label'],'usage':read(case/stage_for(v['label'])/'realize/03-result/usage.json')}
                      for v in variants if resolve_read(case/stage_for(v['label'])/'realize/03-result/usage.json').exists()],
             'prerequisite_audit':prerequisite_audit,'stage17':'PARTIAL' if prerequisite_audit else 'NOT_RUN','stage18':'NOT_RUN','inverse':'DEFERRED_BY_USER'}
    ctx.save(family+'/review.json',summary)
    ctx.save_text(family+'/README.md','# 16번 실행 결과\n\n`plan.json` → 각 유형 `README.md` → `review.json` 순서로 읽습니다.\n'
                  '공통 로그는 문항 루트 `events.jsonl`, 토큰은 각 `realize/03-result/usage.json`입니다.\n'
                  f'뷰어에서 {case.name} → 유형 → 5번 문장과 답변을 선택합니다. 17·18번과 역산은 실행하지 않았습니다.\n')
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',type=Path,required=True); parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--revision'); parser.add_argument('--labels',nargs='+')
    args=parser.parse_args()
    raise SystemExit(0 if run(args.case,args.config,args.revision,args.labels)['status']=='PASS' else 1)
