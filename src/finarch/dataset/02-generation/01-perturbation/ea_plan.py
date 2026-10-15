variant_root = __import__('finarch.dataset.90-operations.stage_paths', fromlist=['variant_root']).variant_root
"""EA01: retain code structure, omit a source value, and evaluate available nodes only."""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

RunContext = __import__('finarch.dataset.90-operations.staging', fromlist=['RunContext']).RunContext
from finarch.dataset.shared.calculation.python_graph import ARITY, OPERATIONS, checked_value, compile_structure, load_graph

_recovery = __import__('finarch.dataset.02-generation.03-validation.ea_recovery', fromlist=['screen_recovery'])
screen_recovery = _recovery.screen_recovery
recovery_descriptor = _recovery.descriptor


def evaluate_available(graph):
    """Missing inputs propagate as states, never as zero, NaN, or old cached values."""
    nodes=graph['nodes'];by_id={n['id']:n for n in nodes}
    if len(by_id)!=len(nodes):raise ValueError('DUPLICATE_NODE_ID')
    expected=Counter((p,n['id'],i) for n in nodes for i,p in enumerate(n['inputs']))
    if expected!=Counter((e['from'],e['to'],e['input_index']) for e in graph['edges']):
        raise ValueError('GRAPH_EDGE_MISMATCH')
    declared=set(graph.get('missing_facts',[]));seen_missing=set();states={};values={};visiting=set()
    def visit(key):
        if key in states:return
        if key in visiting:raise ValueError('GRAPH_CYCLE')
        if key not in by_id:raise ValueError('MISSING_INPUT_NODE')
        visiting.add(key);n=by_id[key];kind=n['kind'];parents=n['inputs']
        if kind in ('fact','constant'):
            if parents:raise ValueError('LEAF_WITH_INPUTS')
            if n.get('availability')=='MISSING':
                if kind!='fact' or n.get('fact_id') not in declared or any(k in n for k in ('value','computed','text')):
                    raise ValueError('INVALID_MISSING_FACT_NODE')
                seen_missing.add(n['fact_id'])
                states[key]={'state':'MISSING','missing_facts':[n['fact_id']]}
            else:
                if kind=='fact' and n.get('fact_id') in declared:raise ValueError('REMOVED_FACT_STILL_HAS_VALUE')
                if n.get('value_type') not in ('int','float'):raise ValueError('INVALID_VALUE_TYPE')
                values[key]=checked_value(int(n['value']) if n['value_type']=='int' else float(n['value']))
                states[key]={'state':'KNOWN','value':str(values[key]),'missing_facts':[]}
        else:
            if kind=='variable':
                if len(parents)!=1:raise ValueError('INVALID_VARIABLE_ARITY')
            elif kind=='operation':
                op=n['operator']
                if op not in OPERATIONS:raise ValueError('UNSUPPORTED_GRAPH_OPERATOR:'+op)
                lo,hi=ARITY[op]
                if not lo<=len(parents)<=hi:raise ValueError('INVALID_OPERATOR_ARITY')
            else:raise ValueError('UNKNOWN_NODE_KIND')
            for p in parents:visit(p)
            missing=sorted({f for p in parents for f in states[p]['missing_facts']})
            if kind=='operation' and n['operator'] in ('/','//','%') and values.get(parents[1])==0:
                raise ValueError('ZERO_DENOMINATOR')
            if missing:states[key]={'state':'BLOCKED','missing_facts':missing}
            else:
                args=[values[p] for p in parents]
                if kind=='operation' and n['operator'] in ('**','pow') and abs(args[1])>10000:raise ValueError('GRAPH_POWER_LIMIT')
                values[key]=checked_value(args[0] if kind=='variable' else OPERATIONS[n['operator']](*args))
                states[key]={'state':'KNOWN','value':str(values[key]),'missing_facts':[]}
        visiting.remove(key)
    for key in by_id:visit(key)
    if graph['output'] not in states:raise ValueError('MISSING_OUTPUT')
    if seen_missing!=declared:raise ValueError('UNREPRESENTED_MISSING_FACT')
    reachable=set()
    def ancestors(key):
        if key in reachable:return
        reachable.add(key)
        for p in by_id[key]['inputs']:ancestors(p)
    ancestors(graph['output'])
    if any(n['kind']=='fact' and n['id'] not in reachable for n in nodes):raise ValueError('FACT_NOT_CONNECTED_TO_ANSWER')
    for name,key in graph['variables'].items():
        if key not in by_id or by_id[key].get('variable')!=name:raise ValueError('INVALID_VARIABLE_MAP')
    return states


def build(program, fact_id):
    # [EA01] The missing value is removed BEFORE the shared AST graph builder runs.
    if fact_id not in program['facts']:raise ValueError('UNKNOWN_DELETION_TARGET')
    branch=deepcopy(program);del branch['facts'][fact_id]
    graph,audit=compile_structure(branch,missing_facts=[fact_id])
    states=evaluate_available(graph)
    for n in graph['nodes']:
        n.pop('computed',None)
        n['evaluation']=states[n['id']]
        if states[n['id']]['state']=='KNOWN':n['computed']=states[n['id']]['value']
    output=states[graph['output']]
    if output['state']!='BLOCKED':raise ValueError('DELETION_NOT_ON_OUTPUT_PATH')
    binding={'code':branch['code'],'facts':{k:{'value':v['value'],'unit':v.get('unit')} for k,v in branch['facts'].items()},
             'missing_facts':[fact_id],'origin':'EA calculation inputs; not the finalized edited context'}
    return graph,binding,audit


README='''# EA · 결측 입력의 계산 그래프

읽는 순서: plan.json → calculation-input.json → graph.json → validation.json.
calculation-input.json에는 원래 코드와 남은 값, 삭제한 근거 키만 있습니다. 삭제값은 계산 입력에 없습니다.
graph.json은 같은 Python AST에서 만든 연결 구조입니다. 값 없는 입력은 MISSING, 이를 필요로 하는 연산·변수는 BLOCKED이며 숫자 computed를 저장하지 않습니다. 다른 입력과 독립 계산은 KNOWN입니다.
plan.json의 원문 위치·삭제 전 인용은 제작용 private 삭제 계획입니다. 원본 코드·본문·기존 그래프는 별도 파일에 보존합니다. 최종 문장 삭제는 아직 하지 않았습니다.

공통 viewer에서 이 실행 → test-0001 → EA → 4 그래프 변경을 선택하면 원본과 결측 그래프, 같은 코드 줄과 연결을 확인합니다. 8 전체 기록에서 이 문서·입력·그래프·검사를 읽습니다. 문제별 events.jsonl에 EA01 시작·산출물·종료가 남습니다.

그래프 구성 성공과 수치 답 계산 불가는 별도 상태입니다. 원래 숫자로 EA 결과를 채우거나 0으로 대체하지 않습니다. Python의 exec를 결측 코드에 실행한 결과가 아니라 공유 AST 파서와 부분 계산기의 결과입니다. 문법 오류·잘못된 이름·알려진 연산 오류는 EA로 처리하지 않고 실패시킵니다.
현재 표시된 경로에서 입력이 부족하다는 확인입니다. 역산·우회와 수학적 답의 비유일성 증명은 미평가이며 EA 성립 완료를 주장하지 않습니다. 추가 LLM 호출은 없습니다.
'''


def create(case_dir,fact_id,label='EA_01'):
    case=Path(case_dir).resolve()
    if Path(label).name!=label or label in ('.','..'):raise ValueError('INVALID_LABEL')
    base=variant_root(label)
    if (case/base).exists():raise ValueError('CANDIDATE_ALREADY_EXISTS')
    original=load_graph(case)  # Enforces gold exclusion and immutable source graph checks.
    paths=['02-calculation/02-prepare-code/03-program.json','03-graph/04-save-graph/01-graph.json','00-data-preparation/01-select-input/01-input.json']
    hashes={p:hashlib.sha256((case/p).read_bytes()).hexdigest() for p in paths}
    program=json.loads((case/paths[0]).read_text())
    program['context']=json.loads((case/paths[2]).read_text())['context']
    ctx=RunContext.resume(case,{},case.name)
    with ctx.trace.activate(),ctx.trace.span('ea_plan.create',stage='04-perturbation/04-plan-ea',step='',role='python') as outcome:
        ctx.save_text(base+'/README.md',README)
        ctx.save(base+'/01-input.json',{'fact_id':fact_id,'selection':'explicit first-case pilot','model_calls':0})
        try:
            graph,binding,audit=build(program,fact_id)
            structure=lambda g:[(n['id'],n['kind'],n['inputs'],n.get('code_line')) for n in g['nodes']]
            if structure(graph)!=structure(original) or graph['edges']!=original['edges']:raise ValueError('CALCULATION_STRUCTURE_CHANGED')
            checks={'structure_built':True,'same_code':binding['code']==program['code'],
                'same_nodes_and_edges':True,'deleted_fact_not_in_inputs':fact_id not in binding['facts'],
                'output_blocked':True,'no_stale_blocked_values':all('computed' not in n and 'value' not in n for n in graph['nodes'] if n['evaluation']['state']!='KNOWN'),
                'original_preserved':all(hashlib.sha256((case/p).read_bytes()).hexdigest()==h for p,h in hashes.items())}
            if not all(checks.values()):raise ValueError('EA_GRAPH_CHECK_FAILED')
            target=deepcopy(program['facts'][fact_id])
            # Original source alignment has already passed load_graph/compile_structure.
            target['text']=program['context'][slice(*target['span'])]
            plan={'axis':'EA','method':'missing-input-dag-v1','fact_id':fact_id,'graphs':{'EA':graph},
                'program_path':base+'/02-calculation-input.json','deletion':{'fact_id':fact_id,'span':target['span'],'before':target['text'],'operation':'delete','status':'PLANNED_NOT_APPLIED'},
                'preserved_inputs_sha256':hashes,'checks':checks,'structure_status':'PASS','calculation_status':'MISSING_EVIDENCE',
                'result':{'answer':None,'missing_facts':[fact_id]},'semantic_status':'NOT_EVALUATED',
                'recovery_review':'SKIPPED_BY_USER','final_text_status':'NOT_RUN','model_calls':0}
            ctx.save(base+'/calculation-input.json',binding);ctx.save(base+'/graph.json',graph)
            ctx.save(base+'/number-normalization.json',audit);ctx.save(base+'/plan.json',plan)
            ctx.save(base+'/validation.json',{'status':'PASS','scope':'graph construction and missing-input propagation only','checks':checks})
            index=case/'04-perturbation/05-list-candidates/03-result.json';index.parent.mkdir(parents=True,exist_ok=True);previous=json.loads(index.read_text())
            if any(v['label']==label for v in previous):raise ValueError('DUPLICATE_VARIANT')
            ctx.save(base+'/previous-variants.json',previous)
            candidate={'label':label,'axis':'EA','status':'NOT_EVALUATED','plan':plan,'reason':'Missing-input graph built; final text, inverse recovery and full EA validity not evaluated'}
            temporary=index.with_suffix('.tmp');temporary.write_text(json.dumps(previous+[candidate],ensure_ascii=False,indent=2)+'\n');temporary.replace(index)
            ctx.trace.artifact('04-perturbation/05-list-candidates/03-result.json');outcome.update(status='PASS',reason='EA_GRAPH_BUILT_WITH_BLOCKED_OUTPUT')
            return {'structure':'PASS','calculation':'MISSING_EVIDENCE','missing_fact':fact_id,'nodes':len(graph['nodes']),'edges':len(graph['edges'])}
        except Exception as error:
            ctx.save(base+'/03-result/failure.json',{'status':'FAIL','reason':str(error)});raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('case_dir');parser.add_argument('fact_id');parser.add_argument('--label',default='EA_01')
    args=parser.parse_args();print(json.dumps(create(args.case_dir,args.fact_id,args.label),ensure_ascii=False))
