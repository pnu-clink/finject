variant_root = __import__('finarch.dataset.90-operations.stage_paths', fromlist=['variant_root']).variant_root
"""Stage 12: a reproducible numeric alternative, not a finished conflict document."""
import argparse
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
RunContext = __import__('finarch.dataset.90-operations.staging', fromlist=['RunContext']).RunContext
from finarch.dataset.shared.calculation.python_graph import load_graph, compile_graph
from finarch.dataset.shared.calculation.python_runtime import execute
from finarch.shared.reference import Reference, normalize
from finarch.dataset.shared.calculation.number_normalization import load_rules, normalize_number


def branch_program(program, context, fact_id, value):
    """Bind one planned alternative for calculation; preserve the original separately."""
    number=Decimal(value)
    if not number.is_finite():raise ValueError('FINITE_ALTERNATIVE_REQUIRED')
    if fact_id not in program['facts']:raise ValueError('UNKNOWN_FACT')
    if number==Decimal(normalize_number(program['facts'][fact_id]['value'],load_rules()[0])[0]):raise ValueError('UNCHANGED_VALUE')
    value=format(number,'f');branch=deepcopy(program)
    # This is an execution binding, NOT a source quotation or the final document.
    prefix=context+'\n[Calculation-only alternative binding] '+fact_id+' = '
    branch['context']=prefix+value
    branch['facts'][fact_id].update(value=value,text=value,span=[len(prefix),len(prefix)+len(value)])
    return branch


def create(case_dir, fact_id, value, label='IC_VALUE_01'):
    # [VP01] docs/02-architecture.md#VP01 — preserve A, calculate a specified B, save evidence.
    case=Path(case_dir).resolve()
    if Path(label).name!=label or label in ('.','..'):raise ValueError('INVALID_LABEL')
    base=f'{variant_root(label)}'
    if (case/base).exists():raise ValueError('CANDIDATE_ALREADY_EXISTS')
    ctx=RunContext.resume(case,{},case.name)
    with ctx.trace.activate(),ctx.trace.span('value_plan.create',stage='04-perturbation/01-plan-ic-value',step='') as outcome:
        ctx.save('04-perturbation/01-plan-ic-value/01-select-target/01-input.json',{'fact_id':fact_id,'alternative_value':value,'selection':'explicit pilot value; not a distribution policy','model_calls':0})
        try:
            original=load_graph(case)
            program=json.loads((case/'02-calculation/02-prepare-code/03-program.json').read_text())
            sample=json.loads((case/'00-data-preparation/01-select-input/01-input.json').read_text())
            original_hash=hashlib.sha256((case/'03-graph/04-save-graph/01-graph.json').read_bytes()).hexdigest()
            branch=branch_program(program,sample['context'],fact_id,value)
            ctx.save('04-perturbation/01-plan-ic-value/02-change-value/01-program.json',branch)
            execution=execute(branch,save=lambda name,data:ctx.save(base+'/'+name,data))
            ctx.save(base+'/python-execution.json',{'status':execution.status,'reason':execution.reason,'data':execution.data})
            if execution.status!='PASS':raise ValueError('ALTERNATIVE_PYTHON_FAILED:'+execution.reason)
            graph,raw,audit=compile_graph(branch)
            nodes={n['id']:n for n in graph['nodes']}
            if str(raw)!=execution.data['exact_value'] or any(str(nodes[node]['computed'])!=execution.data['trace'].get(name) for name,node in graph['variables'].items()):raise ValueError('ALTERNATIVE_GRAPH_PYTHON_MISMATCH')
            ref=Reference(**{key:sample[key] for key in ('reference_answer','reference_answer_type','reference_precision')})
            a_raw=next(n['computed'] for n in original['nodes'] if n['id']==original['output'])
            a,b=normalize(a_raw,ref),normalize(str(raw),ref)
            if a==b:raise ValueError('FINAL_ANSWER_UNCHANGED')
            if program['code']!=branch['code']:raise ValueError('CALCULATION_CHANGED')
            if hashlib.sha256((case/'03-graph/04-save-graph/01-graph.json').read_bytes()).hexdigest()!=original_hash:raise ValueError('ORIGINAL_GRAPH_CHANGED')
            # Planned evidence B is not represented as an original-context span.
            for node in graph['nodes']:
                if node.get('fact_id')==fact_id:
                    node.pop('span',None);node['evidence_origin']='planned_alternative';node['original_span']=program['facts'][fact_id]['span']
            plan={'axis':'IC_VALUE','method':'deterministic-explicit-alternative-v1','fact_id':fact_id,
                  'value_pair':[program['facts'][fact_id]['value'],branch['facts'][fact_id]['value']],
                  'original_evidence':program['facts'][fact_id],
                  'alternative_evidence':{'value':branch['facts'][fact_id]['value'],'unit':program['facts'][fact_id].get('unit'),'target':'same quantity and period as A','source_conditions':'unchanged','origin':'planned; not extracted from original'},
                  'original_graph_sha256':original_hash,'graphs':{'B':graph},
                  'answers':{'A':{'raw':a_raw,'computed':a},'B':{'raw':str(raw),'computed':b},'precision':ref.reference_precision,'reference_type':ref.reference_answer_type},
                  'checks':{'same_code':True,'original_preserved':True,'python_graph_equal':True,'different_final_answers':True},
                  'recovery_review':{'status':'SKIPPED_BY_USER','reason':'Stage 11 deferred this iteration'},
                  'semantic_status':'NOT_EVALUATED','final_text_status':'NOT_RUN',
                  'note':'Only calculation branch B was checked. A is preserved. Text generation and semantic auditing follow; bypass review is deferred.'}
            ctx.save(base+'/plan.json',plan)
            ctx.save(base+'/04-check-target/03-result.json',{'status':'PASS','reason':'CALCULATION_PLAN_VERIFIED_ONLY','data':plan['checks']})
            ctx.save_text(base+'/README.md','# The value collision plan 12\n\nWe saved the original A and calculated it in Python code and graphs, like the B alternative of one value. plan.json is A/B values and the calculation graph. 11The bar was omitted by the user\'s decision. 0In the events.jsonl of the problem, check the start, finish, time and time. 4You pick a candidate from the bar.\n')
            variant={'label':label,'axis':'IC_VALUE','status':'NOT_EVALUATED','calculation_status':'PASS','plan':plan,'reason':'Calculation plan checked; final text and conflict semantics not evaluated'}
            index=case/'04-perturbation/05-list-candidates/03-result.json';index.parent.mkdir(parents=True,exist_ok=True);existing=json.loads(index.read_text()) if index.exists() else []
            if any(v['label']==label for v in existing):raise ValueError('DUPLICATE_VARIANT')
            tmp=index.with_suffix('.tmp');tmp.write_text(json.dumps(existing+[variant],ensure_ascii=False,indent=2)+'\n');tmp.replace(index);ctx.trace.artifact('04-perturbation/05-list-candidates/03-result.json')
            outcome.update(status='PASS',reason='CALCULATION_PLAN_VERIFIED_ONLY')
            return {'case':case.name,'candidate':label,'answer_A':a,'answer_B':b,'calculation_status':'PASS','semantic_status':'NOT_EVALUATED','model_calls':0}
        except Exception as error:
            ctx.save(base+'/03-result/failure.json',{'status':'FAIL','reason':str(error)})
            outcome.update(status='FAIL',reason=str(error));raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--case',required=True);p.add_argument('--fact',required=True);p.add_argument('--value',required=True);args=p.parse_args()
    print(json.dumps(create(args.case,args.fact,args.value),ensure_ascii=False))
