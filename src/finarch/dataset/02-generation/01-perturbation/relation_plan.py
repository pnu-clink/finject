variant_root = __import__('finarch.dataset.90-operations.stage_paths', fromlist=['variant_root']).variant_root
"""Stage 14 pilot: explicit positive-ratio relation and one selected calculation direction."""
import argparse
import ast
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
RunContext = __import__('finarch.dataset.90-operations.staging', fromlist=['RunContext']).RunContext
from finarch.dataset.shared.calculation.python_graph import load_graph, compile_graph
from finarch.dataset.shared.calculation.python_runtime import execute
from finarch.shared.reference import Reference, normalize
fact_decimal = __import__('finarch.dataset.02-generation.01-perturbation.relation_scope', fromlist=['fact_decimal']).fact_decimal


def describe_relation_properties(plan):
    # [RP02] T091: record the operation on a quantity, not a second claimed amount.
    relation = plan['relation']; branch = plan['branches']['B']
    return {
        'change_kind': 'operation_on_quantity',
        'target': {'kind': 'source_quantity', 'id': relation['left']},
        'operand': {'kind': 'source_quantity', 'id': relation['right']},
        'operation': {'operator': 'multiply', 'parameter': relation['multiplier'], 'parameter_role': 'multiplier'},
        'expression': relation['expression'],
        'application': {'branch': 'B', 'variable': branch['derived_variable'],
                        'code_line': branch['relation_code_line'], 'node_ids': branch['relation_node_ids']},
        'scope': {key: plan['scope'][key] for key in ('entity', 'period', 'unit')},
        'preserve_original_observations': True,
        'preserve_question_calculation': branch['question_calculation_unchanged'],
    }


def split_inputs(program):
    tree=ast.parse(program['code']); inputs=[]; tail=[]
    for stmt in tree.body:
        is_input=(isinstance(stmt,ast.Assign) and len(stmt.targets)==1
            and isinstance(stmt.targets[0],ast.Name) and isinstance(stmt.value,ast.Call)
            and isinstance(stmt.value.func,ast.Name) and stmt.value.func.id=='fact'
            and len(stmt.value.args)==1 and isinstance(stmt.value.args[0],ast.Constant)
            and isinstance(stmt.value.args[0].value,str))
        if is_input and not tail: inputs.append(stmt)
        else: tail.append(stmt)
    binding={s.value.args[0].value:s.targets[0].id for s in inputs}
    if set(binding)!=set(program['facts']) or len(binding)!=len(inputs):
        raise ValueError('UNSUPPORTED_INPUT_LAYOUT')
    return inputs,tail,binding


def make_branches(program,context,left,right,ratio,*,directions=("B",)):
    # [RP01] One selected direction by default; reverse calculation is optional, not this run scope.
    if not directions or len(set(directions))!=len(directions) or any(d not in ("B","C") for d in directions):raise ValueError("INVALID_RELATION_DIRECTION")
    k=Decimal(str(ratio))
    if not k.is_finite() or k<=0:raise ValueError('POSITIVE_FINITE_RATIO_REQUIRED')
    if left==right or left not in program['facts'] or right not in program['facts']:
        raise ValueError('TWO_DISTINCT_FACTS_REQUIRED')
    lhs,rhs=program['facts'][left],program['facts'][right]
    if not lhs.get('unit') or lhs.get('unit')!=rhs.get('unit'):raise ValueError('SAME_UNIT_REQUIRED')
    if fact_decimal(lhs['value'])==k*fact_decimal(rhs['value']):raise ValueError('RELATION_ALREADY_CONSISTENT')
    inputs,tail,binding=split_inputs(program)
    names={n.id for n in ast.walk(ast.parse(program['code'])) if isinstance(n,ast.Name)}
    if 'relation_multiplier' in names:raise ValueError('RELATION_VARIABLE_COLLISION')
    result={}
    for label,target,anchor,op in [('B',left,right,'*'),('C',right,left,'/')]:
        if label not in directions:continue
        branch=deepcopy(program);branch['context']=context
        # Only this conditional execution omits the conflicting observation; the original document is immutable.
        del branch['facts'][target]
        prefix=[ast.unparse(s) for s in inputs if s.value.args[0].value!=target]
        relation_line=len(prefix)+2
        prefix += [f'relation_multiplier = {format(k,"f")}',f'{binding[target]} = {binding[anchor]} {op} relation_multiplier']
        branch['code']='\n'.join(prefix+ [ast.unparse(s) for s in tail])
        result[label]={'program':branch,'retained_observation':anchor,'omitted_observation':target,
            'derived_variable':binding[target],'relation_code_line':relation_line,
            'condition':f'{anchor} observation + {left} = {format(k,"f")} * {right}',
            'question_calculation_unchanged':ast.dump(ast.Module(body=tail,type_ignores=[]))==ast.dump(ast.Module(body=ast.parse(branch['code']).body[len(prefix):],type_ignores=[]))}
    return result


def create(case_dir):
    # [RP01] First-case scope is deliberate; arbitrary financial relations require separate eligibility review.
    case=Path(case_dir).resolve();label='IC_RELATION_01';base=f'{variant_root(label)}'
    if (case/base).exists():raise ValueError('CANDIDATE_ALREADY_EXISTS')
    original=load_graph(case)
    program=json.loads((case/'02-calculation/02-prepare-code/03-program.json').read_text());sample=json.loads((case/'00-data-preparation/01-select-input/01-input.json').read_text())
    left,right='service_fee_income','commission_income'
    if sample.get('raw_id')!='finance-test-489':raise ValueError('PILOT_SCOPE_ONLY')
    inputs=['02-calculation/02-prepare-code/03-program.json','00-data-preparation/01-select-input/01-input.json','03-graph/04-save-graph/01-graph.json']
    hashes={p:hashlib.sha256((case/p).read_bytes()).hexdigest() for p in inputs}
    ctx=RunContext.resume(case,{},case.name)
    with ctx.trace.activate(),ctx.trace.span('relation_plan.create',stage='03-graph',step='RP01') as outcome:
        ctx.save(base+'/01-input.json',{'left':left,'right':right,'ratio':'2','model_calls':0,'selection':'explicit first-case pilot'})
        # README is generated from this shared template on success or failure.
        ctx.save_text(base+'/README.md',README)
        try:
            branches=make_branches(program,sample['context'],left,right,'2')
            ref=Reference(**{k:sample[k] for k in ('reference_answer','reference_answer_type','reference_precision')})
            a=next(n['computed'] for n in original['nodes'] if n['id']==original['output'])
            answers={'A':{'raw':a,'computed':normalize(a,ref)}};graphs={};details={}
            for key,branch in branches.items():
                bp=branch['program'];path=base+'/'+key
                ctx.save(path+'/program.json',bp)
                execution=execute(bp,save=lambda name,data:ctx.save(path+'/'+name,data))
                ctx.save(path+'/python-execution.json',{'status':execution.status,'reason':execution.reason,'data':execution.data})
                if execution.status!='PASS':raise ValueError('BRANCH_EXECUTION_FAILED:'+key+':'+execution.reason)
                graph,raw,_=compile_graph(bp)
                values={n['id']:n['computed'] for n in graph['nodes']}
                if str(raw)!=execution.data['exact_value'] or any(values[node]!=execution.data['trace'].get(name) for name,node in graph['variables'].items()):
                    raise ValueError('GRAPH_PYTHON_MISMATCH:'+key)
                if not branch['question_calculation_unchanged']:raise ValueError('QUESTION_CALCULATION_CHANGED')
                relation_ids=[n['id'] for n in graph['nodes'] if n.get('code_line')==branch['relation_code_line']]
                for n in graph['nodes']:
                    if n['id'] in relation_ids:n['evidence_origin']='planned_relation'
                ctx.save(path+'/graph.json',graph)
                graphs[key]=graph;answers[key]={'raw':str(raw),'computed':normalize(str(raw),ref)}
                details[key]={k:v for k,v in branch.items() if k!='program'}|{'relation_node_ids':relation_ids,'program_path':path+'/program.json','python_graph_equal':True}
            if any(answers[k]['computed']==answers['A']['computed'] for k in branches):raise ValueError('FINAL_ANSWER_UNCHANGED')
            if any(hashlib.sha256((case/p).read_bytes()).hexdigest()!=h for p,h in hashes.items()):raise ValueError('ORIGINAL_CHANGED')
            plan={'axis':'IC_RELATION','method':'explicit-positive-ratio-v1','relation':{'left':left,'right':right,'multiplier':'2','expression':left+' = 2 * '+right,'origin':'synthetic planned relation; not original evidence'},
                'scope':{'entity':'the same local bank','period':'the same past quarter','unit':'dollars','input_precision':'whole-dollar pilot values; no rounded ratio observation','eligibility':'first-case review only'},
                'original_evidence':{left:program['facts'][left],right:program['facts'][right]},'preserved_inputs_sha256':hashes,
                'branch_enumeration':{'scope':'one selected direction; original observations versus right observation plus relation','selected_branches':['A','B'],'reverse_direction':'DEFERRED_BY_USER','not_claimed':'all possible conditional answers'},
                'branches':details,'graphs':graphs,'answers':answers|{'precision':ref.reference_precision},
                'editing':{'operation':'insert','anchor':sample['context'].index(" The bank's financial analyst"),'preserve_original_context':True,'preserve_question':True,'final_text_status':'NOT_RUN'},
                'checks':{'original_preserved':True,'python_graph_equal':True,'question_calculation_unchanged':True,'different_final_answers':True,'selected_direction_verified':True},
                'semantic_status':'NOT_EVALUATED','final_text_status':'NOT_RUN','recovery_review':'SKIPPED_BY_USER','model_calls':0,'relation_selection':'agent_selected_pilot; not automatic relation discovery'}
            plan['relation']['properties'] = describe_relation_properties(plan)
            ctx.save(base+'/plan.json',plan)
            ctx.save(base+'/04-check-target/03-result.json',{'status':'PASS','reason':'RATIO_PILOT_CALCULATION_ONLY','data':plan['checks']})
            index=case/'04-perturbation/05-list-candidates/03-result.json';existing=json.loads(index.read_text())
            if any(v['label']==label for v in existing):raise ValueError('DUPLICATE_VARIANT')
            ctx.save(base+'/previous-variants.json',existing)
            variant={'label':label,'axis':'IC_RELATION','status':'NOT_EVALUATED','calculation_status':'PASS','plan':plan,'reason':'Original and one relation direction checked; final text and semantics not evaluated'}
            tmp=index.with_suffix('.tmp');tmp.write_text(json.dumps(existing+[variant],ensure_ascii=False,indent=2)+'\n');tmp.replace(index);ctx.trace.artifact('04-perturbation/05-list-candidates/03-result.json')
            save_relation = __import__('finarch.dataset.02-generation.02-generate-text.text_preview', fromlist=['save_relation']).save_relation
            save_relation(case, label)
            outcome.update(status='PASS',reason='SELECTED_RATIO_BRANCH_VERIFIED')
            return {'answers':answers,'model_calls':0,'scope':'first-case ratio plan only'}
        except Exception as error:
            ctx.save(base+'/03-result/failure.json',{'status':'FAIL','reason':str(error)});outcome.update(status='FAIL',reason=str(error));raise

README='''# IC-RELATION · 14First relationship plan

Readings: additional relationship of plan.json; selected quarter; conditional part answer → program.json and graph.json of B → python-execution.json → 04-check-target/03-result.json.

It preserves the original and the original numbers. It doesn't just adopt one observation based on the relationship, but it calculates the variable based on the B execution copy. This is not a deletion of the finished context. The cumulative calculation of the questions is the same. The relationship sentence is a local draft, not the actual LLM response or final thesis.

It calculates only one direction of application of the relationship, depending on the user's decision. The opposite direction does not mean that it is omitted from this range and that it has all the possible answers. It is not a complete verification of the whole subset of the original, of all financial relationships.

The viewer takes a linear formula from the storage graph and compares the original to the relationship application. The flower is the original observation, the orange is the relationship application and it doesn't change the execution code.

The problem is that events.jsonl has a start, finish, run time.0001 → IC-RELATION → Graph change, you can see the source and a relationship path code. The phrases and answers show the source language, the relationship application, and the preview of the source/item editing below. 16So, what's the meaning of the test? 17And the LLM call is 0calls.
'''


def select_single_direction(case_dir):
    """Preserve old plan/artifacts and activate an A/B-only revision without recalculation."""
    case=Path(case_dir).resolve();base='04-perturbation/03-plan-ic-relation';ctx=RunContext.resume(case,{},case.name)
    if (case/base/'plan-v2.json').exists():raise ValueError('SINGLE_DIRECTION_REVISION_EXISTS')
    load_graph(case)
    with ctx.trace.activate(),ctx.trace.span('relation_plan.select_direction',stage='03-graph',step='RP01-scope') as outcome:
        original=json.loads((case/base/'plan.json').read_text());plan=deepcopy(original)
        plan['branches']={'B':plan['branches']['B']};plan['graphs']={'B':plan['graphs']['B']};plan['answers']={k:v for k,v in plan['answers'].items() if k!='C'}
        plan['branch_enumeration']={'scope':'one selected direction; not exhaustive answers','selected_branches':['A','B'],'reverse_direction':'DEFERRED_BY_USER','historical_plan':'plan.json'}
        plan['checks'].pop('three_pattern_branches',None);plan['checks']['selected_direction_verified']=True
        plan['relation_selection']='agent_selected_pilot; not automatic relation discovery'
        plan['revision']=2
        ctx.save(base+'/plan-v2.json',plan)
        ctx.save_text(base+'/README-v2.md',README+'\nNow I\'m reading plan-v2.json and B/. plan.json and C/ are preserved in the previous record, excluding active candidates and viewers.\n')
        existing=json.loads((case/'04-perturbation/05-list-candidates/03-result.json').read_text());ctx.save(base+'/variants-before-v2.json',existing)
        for variant in existing:
            if variant['label']=='IC_RELATION_01':variant.update(plan=plan,reason='Original and one relation direction checked; reverse direction omitted; final semantics not evaluated')
        index=case/'04-perturbation/05-list-candidates/03-result.json';tmp=index.with_suffix('.tmp');tmp.write_text(json.dumps(existing,ensure_ascii=False,indent=2)+'\n');tmp.replace(index);ctx.trace.artifact('04-perturbation/05-list-candidates/03-result.json')
        ctx.save(base+'/scope-v2.json',{'status':'PASS','selected':['A','B'],'deferred':['C'],'reason':'user requested one relation calculation','recalculated':False,'pipeline_model_calls':0})
        outcome.update(status='PASS',reason='ONE_RELATION_DIRECTION_ACTIVE')
        return {'active':['A','B'],'historical':['C']}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--case',required=True);args=p.parse_args()
    print(json.dumps(create(args.case),ensure_ascii=False))
