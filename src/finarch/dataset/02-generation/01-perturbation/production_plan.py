variant_root = __import__('finarch.dataset.90-operations.stage_paths', fromlist=['variant_root']).variant_root
"""PB01: explicit, source-grounded first-ten recipes using shared calculation gates.

These recipes are selected by the agent from actual source documents; they are
not a claimed automatic relation-discovery algorithm. Final prose uses R16 CLI.
"""
import ast
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re

RunContext = __import__('finarch.dataset.90-operations.staging', fromlist=['RunContext']).RunContext
apply_patches = __import__('finarch.dataset.90-operations.staging', fromlist=['apply_patches']).apply_patches
value_plan = __import__('finarch.dataset.02-generation.01-perturbation.value_plan', fromlist=['*'])
source_plan = __import__('finarch.dataset.02-generation.01-perturbation.source_plan', fromlist=['*'])
ea_plan = __import__('finarch.dataset.02-generation.01-perturbation.ea_plan', fromlist=['*'])
read = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['read']).read
digest = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['digest']).digest
numbers = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['numbers']).numbers
slot = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['slot']).slot
from finarch.dataset.shared.calculation.python_graph import load_graph, compile_graph
from finarch.dataset.shared.calculation.python_runtime import execute
from finarch.dataset.schemas.registry import describe
from finarch.dataset.schemas.validation import validate
from finarch.shared.reference import Reference, normalize
from finarch.dataset.shared.calculation.number_normalization import prepare_numeric_values
relation_scope = __import__('finarch.dataset.02-generation.01-perturbation.relation_scope', fromlist=['*'])


def source_program(case):
    raw=read(case/'02-calculation/02-prepare-code/03-program.json');raw['context']=read(case/'00-data-preparation/01-select-input/01-input.json')['context']
    return prepare_numeric_values(raw)[0]


def boundaries(context, span):
    """A table row is atomic; sentence dots inside decimals are not boundaries."""
    a,b=span
    line_a=context.rfind('\n',0,a)+1;line_b=context.find('\n',b)
    if line_b<0:line_b=len(context)
    if '|' in context[line_a:line_b]:return [line_a,line_b]
    ends=[m.end() for m in re.finditer(r'[.!?](?=\s|$)',context)]
    start=max([0]+[e for e in ends if e<=a]);end=min([len(context)]+[e for e in ends if e>=b])
    while start<a and context[start].isspace():start+=1
    return [start,end]


def numeric_list(text):
    return [str(n) for n,count in numbers(text).items() for _ in range(count)]


def index_save(ctx, items):
    p=ctx.root/'04-perturbation/05-list-candidates/03-result.json';p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix('.tmp')
    tmp.write_text(json.dumps(items,ensure_ascii=False,indent=2)+'\n');tmp.replace(p)
    ctx.trace.artifact('04-perturbation/05-list-candidates/03-result.json')


README='''# 실제 원문 기반 변경 계획

읽는 순서: generation-spec.json(선정 대상·기간·단위·연산·삭제 범위) → variants.json → 유형별 plan.json과 Python/그래프 검사 → 05-text의 실제 생성·감사 기록.
이 계획은 현재 10문항의 실제 원문을 읽고 에이전트가 지정했습니다. 자동 관계 발견이나 실제 출처 진위를 주장하지 않습니다. 문장 초안을 만들지 않으며 16번의 실제 응답만 완성 본문으로 씁니다.
숫자·원본 코드·질문은 원본 파일에 보존합니다. 역산·우회 및 답의 비유일성 증명은 보류입니다. 질문에 남는 EA 값은 불가 사유를 기록하고 생성하지 않습니다.
공통 뷰어에서 문항 → 유형 → 4 그래프 변경, 5 문장과 답변, 6 사람 판정으로 읽습니다. events.jsonl은 실제 실행 중 기록되며 18번은 제작에서 호출하지 않습니다.
'''


def relation_create(case, spec):
    ctx=RunContext.resume(case,{},case.name);root='04-perturbation/03-plan-ic-relation'
    sample=read(case/'00-data-preparation/01-select-input/01-input.json');program=source_program(case);original=load_graph(case)
    r=spec['relation'];target=r['target'];operand=r['operand'];factor=Decimal(r['factor'])
    if target not in program['facts'] or operand not in program['facts'] or target==operand or factor<=0 or not factor.is_finite():
        raise ValueError('INVALID_RELATION_OPERANDS')
    descriptors,_,cells=relation_scope.descriptors(sample['context'],program)
    scoped={d['fact_id']:d for d in descriptors}
    relation_scope.check_structure(scoped[target],scoped[operand],str(factor),cells)
    if (program['facts'][target]['unit'] or '').strip()!=(program['facts'][operand]['unit'] or '').strip():raise ValueError('RELATION_UNIT_MISMATCH')
    tree=ast.parse(program['code']);bindings={};last=-1
    for i,node in enumerate(tree.body):
        if isinstance(node,ast.Assign) and isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Name) and node.value.func.id=='fact':
            bindings[node.value.args[0].value]=node.targets[0].id;last=i
    if set(bindings)!=set(program['facts']):raise ValueError('RELATION_INPUT_BINDING_INCOMPLETE')
    newvar='perturbed_'+bindings[target];names={n.id for n in ast.walk(tree) if isinstance(n,ast.Name)}
    if newvar in names or 'relation_multiplier' in names:raise ValueError('RELATION_NAME_COLLISION')
    class Substitute(ast.NodeTransformer):
        def visit_Name(self,node):
            return ast.copy_location(ast.Name(id=newvar,ctx=node.ctx),node) if isinstance(node.ctx,ast.Load) and node.id==bindings[target] else node
    prefix=[ast.unparse(n) for n in tree.body[:last+1] if not (target!=operand and isinstance(n,ast.Assign)
            and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='fact'
            and n.value.args[0].value==target)]
    tail=[Substitute().visit(deepcopy(n)) for n in tree.body[last+1:]]
    prefix+=['relation_multiplier = '+str(factor),f'{newvar} = {bindings[operand]} * relation_multiplier']
    line=len('\n'.join(prefix).splitlines())
    branch={**deepcopy(program),'context':sample['context'],'code':'\n'.join(prefix+[ast.unparse(n) for n in tail])}
    if target!=operand:del branch['facts'][target]
    with ctx.trace.activate(),ctx.trace.span('production.relation',stage='04-perturbation/03-plan-ic-relation',step='',role='python'):
        ctx.save(root+'/01-select-target-and-operation/01-input.json',r)
        ctx.save(root+'/02-apply-relation/01-program.json',branch)
        execution=execute(branch,save=lambda n,v:ctx.save(root+'/03-check-calculation/'+n,v))
        if execution.status!='PASS':raise ValueError('RELATION_PYTHON_FAILED:'+execution.reason)
        graph,raw,_=compile_graph(branch)
        nodes={n['id']:n for n in graph['nodes']}
        if str(raw)!=execution.data['exact_value'] or any(str(nodes[n]['computed'])!=execution.data['trace'].get(k) for k,n in graph['variables'].items()):raise ValueError('RELATION_GRAPH_MISMATCH')
        ref=Reference(**{k:sample[k] for k in ('reference_answer','reference_answer_type','reference_precision')})
        a=next(n['computed'] for n in original['nodes'] if n['id']==original['output'])
        answers={'A':{'raw':a,'computed':normalize(a,ref)},'B':{'raw':str(raw),'computed':normalize(str(raw),ref)},'precision':ref.reference_precision}
        if answers['A']['computed']==answers['B']['computed']:raise ValueError('FINAL_ANSWER_UNCHANGED')
        relation_ids=[n['id'] for n in graph['nodes'] if n.get('code_line')==line]
        for n in graph['nodes']:
            if n['id'] in relation_ids:n['evidence_origin']='planned_relation'
        preserved={p:digest(case/p) for p in ('02-calculation/02-prepare-code/03-program.json','00-data-preparation/01-select-input/01-input.json','03-graph/04-save-graph/01-graph.json')}
        properties={'change_kind':'operation_on_quantity','target':{'kind':'source_quantity','id':target},
                    'operand':{'kind':'source_quantity','id':operand},'operation':{'operator':'multiply','parameter':str(factor),'parameter_role':'multiplier'},
                    'expression':f'{target} = {factor} * observed({operand})','scope':r['scope'],
                    'preserve_original_observations':True,
                    'application':{'branch':'B','variable':newvar,'code_line':line,'node_ids':relation_ids}}
        plan={'axis':'IC_RELATION','method':'scoped-operation-v1','relation':{'left':target,'right':operand,'multiplier':str(factor),
              'expression':properties['expression'],'properties':properties},'scope':r['scope'],
              'original_evidence':{k:program['facts'][k] for k in {target,operand}},'preserved_inputs_sha256':preserved,
              'branches':{'B':{'derived_variable':newvar,'relation_code_line':line,'relation_node_ids':relation_ids,'program_path':root+'/02-apply-relation/01-program.json','question_calculation_unchanged':True}},
              'graphs':{'B':graph},'answers':answers,'editing':{'anchor':spec['anchor'][1],'operation':'insert','preserve_original_context':True,'preserve_question':True},
              'checks':{'original_preserved':True,'python_graph_equal':True,'different_final_answers':True,'question_tail_preserved_except_operand_binding':True},
              'semantic_status':'NOT_EVALUATED','final_text_status':'NOT_RUN','model_calls':0,'recovery_review':'SKIPPED_BY_USER'}
        ctx.save(root+'/plan.json',plan);ctx.save(root+'/03-check-calculation/01-graph.json',graph)
        ctx.save(root+'/03-check-calculation/02-execution.json',{'status':execution.status,'data':execution.data})
        ctx.save_text(root+'/README.md',README)
        items=read(case/'04-perturbation/05-list-candidates/03-result.json');items.append({'label':'IC_RELATION_01','axis':'IC_RELATION','status':'NOT_EVALUATED','plan':plan});index_save(ctx,items)
        preview={'axis':'IC_RELATION','status':'NOT_RUN','original_context':sample['context'],'question':sample['question'],
                 'preview_context':sample['context'],'patches':[],'conditional_answers':answers,'python':{'A':program['code'],'B':branch['code']},
                 'target':{'relation':plan['relation'],'scope':plan['scope']},'origin':'planned operation; final text awaiting LLM'}
        ctx.save(root+'/05-text-input-preview.json',preview)


def ea_preview(case, spec, label, key):
    ctx=RunContext.resume(case,{},case.name);root=variant_root(label)
    sample=read(case/'00-data-preparation/01-select-input/01-input.json');program=source_program(case);plan=read(case/root/'plan.json')
    c=sample['context'];fact=program['facts'][key];a,b=fact['span'];e=spec['ea'][key];start,end=e['span']
    if not start<=a<b<=end or c[a:b]!=fact['text']:raise ValueError('EA_TARGET_RANGE_MISMATCH')
    ids=[n['id'] for n in plan['graphs']['EA']['nodes'] if n.get('fact_id')==key]
    tag=f'[EA_DELETE:{key}]';tagged=c[:a]+tag+c[b:]
    preview={'axis':'EA','status':'NOT_RUN','final_text_status':'NOT_RUN','semantic_status':'NOT_EVALUATED','model_calls':0,
             'original_context':c,'question':sample['question'],'patches':[],
             'intermediate':{'context':tagged,'tag':tag,'patches':[{'start':a,'end':b,'before':fact['text'],'text':tag,'element_ids':ids}]},
             'target':plan['deletion'],'python':{'code':program['code'],'missing_facts':[key]},
             'graph_binding':{'missing_node_ids':ids,'blocked_node_ids':[n['id'] for n in plan['graphs']['EA']['nodes'] if n['evaluation']['state']=='BLOCKED']},
             'calculation_result':plan['result'],'origin':'structured deletion plan; no drafted sentence'}
    ctx.save(root+'/05-text-input-preview.json',preview)
    ctx.save(root+'/04-deletion-check.json',{'status':'PASS','scope':'selected input and source range only; no generated text yet',
             'checks':{**plan['checks'],'source_range_verified':True},
             'selection':{'fact_id':key,'kind':'observed_input','input_order':list(program['facts']).index(key)+1},'recovery_review':'DEFERRED_BY_USER'})
    ctx.save_text(root+'/05-text-input-preview.md',README)


def prepare(case_dir, spec):
    case=Path(case_dir).resolve();sample=read(case/'00-data-preparation/01-select-input/01-input.json');program=source_program(case);graph=load_graph(case)
    if (case/'04-perturbation/00-receive-input/01-input.json').exists():raise ValueError('PRODUCTION_PLAN_ALREADY_EXISTS')
    spec=deepcopy(spec)
    from finarch.shared.providers.input_policy import reject_preconstructed
    reject_preconstructed(spec)
    target=spec['target'];fact=program['facts'][target]
    spec['anchor']=boundaries(sample['context'],fact['span']);spec['version']='source-grounded-first-ten-v1'
    spec['selection_origin']='agent reviewed actual source and Python inputs; not automatic discovery'
    for k,e in spec['ea'].items():
        f=program['facts'][k]
        if e.get('blocked'):continue
        if e.get('table'):
            a,b=f['span']
            if sample['context'][a:a+1]=='$':pass
            elif a and sample['context'][a-1]=='$':a-=1
            e.update(span=[a,b])
        else:e['span']=boundaries(sample['context'],f['span'])
    ctx=RunContext.resume(case,{},case.name)
    ctx.save('04-perturbation/00-receive-input/01-input.json',spec);ctx.save_text('04-perturbation/README.md',README)
    value_plan.create(case,target,spec['alternative'])
    ctx=RunContext.resume(case,{},case.name)
    base=read(case/'04-perturbation/01-plan-ic-value/03-check-calculation/plan.json');ids=[n['id'] for n in graph['nodes'] if n.get('fact_id')==target]
    payload={'axis':'IC_VALUE','original_context':sample['context'],'question':sample['question'],
             'target':{'fact_id':target,'original_span':fact['span'],'original_text':fact['text'],'unit':fact['unit'],
                       'nearby_sentence':{'span':spec['anchor'],'text':sample['context'][slice(*spec['anchor'])]}},
             'claims':{'A':{'value':base['value_pair'][0]},'B':{'value':base['value_pair'][1]}},'source_conditions':[],
             'conditional_answers':base['answers'],'python':{'code':program['code']},'graph_binding':{'original_node_ids':ids}}
    pair_id=case.parent.name+':'+case.name+':IC_VALUE_01:position-v1'
    items=[]
    for pos in ('before','after'):
        p={**deepcopy(payload),'status':'NOT_RUN','patches':[],
           'claim_order':['B','A'] if pos=='before' else ['A','B'],
           'target_sentence':{'text':payload['target']['nearby_sentence']['text'],'original_span':spec['anchor']},
           'origin':'structured insertion plan; no drafted sentence'}
        label='IC_VALUE_01_'+pos.upper();root=variant_root(label)
        plan={'axis':'IC_VALUE','base_plan_ref':'04-perturbation/01-plan-ic-value/03-check-calculation/plan.json',
              'base_plan_sha256':digest(case/'04-perturbation/01-plan-ic-value/03-check-calculation/plan.json'),
              'pair_id':pair_id,'perturb_position':pos,'claim_order':p['claim_order'],'target_sentence':p['target_sentence']}
        ctx.save(root+'/plan.json',plan);ctx.save(root+'/05-text-input-preview.json',p);ctx.save(root+'/06-generation-input.json',payload)
        ctx.save_text(root+'/README.md',README)
        items.append({'label':label,'axis':'IC_VALUE','status':'NOT_EVALUATED','plan':plan,'pair_id':pair_id,'perturb_position':pos})
    index_save(ctx,items);source_plan.create(case)
    ctx=RunContext.resume(case,{},case.name)
    for label in ('IC_SOURCE_A_ONLY','IC_SOURCE_B_ONLY'):
        root=variant_root(label)
        ctx.save(root+'/06-generation-input.json',payload)
        ctx.save(root+'/05-text-input-preview.json',{'axis':'IC_SOURCE','status':'NOT_RUN','original_context':sample['context'],
                 'preview_context':sample['context'],'question':sample['question'],'patches':[],
                 'conditional_answers':base['answers'],'target':payload['target'],'python':payload['python'],'graph_binding':payload['graph_binding']})
    if spec.get('relation'):
        relation_create(case,spec)
    else:
        ctx.save('04-perturbation/03-plan-ic-relation/not-generated.json',{
            'status':'NOT_EVALUATED','reason':spec['relation_unavailable'],'model_calls':0})
    for i,(key,e) in enumerate(spec['ea'].items()):
        ctx=RunContext.resume(case,{},case.name)
        label=('EA_01','EA_02')[i]
        if e.get('blocked'):
            ctx.save(variant_root(label)+'/not-generated.json',{'status':'NOT_EVALUATED','reason':e['blocked'],'fact_id':key,'model_calls':0})
            continue
        ea_plan.create(case,key,label);ea_preview(case,spec,label,key)
    return {'case':case.name,'variants':len(read(case/'04-perturbation/05-list-candidates/03-result.json'))}


def realization_request(case, variant, sample, program, graph, base, preview, value_sentence):
    """PB02: project only actual scoped slots into the existing response-schema path."""
    spec=read(case/'04-perturbation/00-receive-input/01-input.json')
    from finarch.shared.providers.input_policy import reject_preconstructed
    reject_preconstructed(spec)
    axis=variant['axis'];plan=variant['plan'];c=sample['context'];tagged=None
    program=source_program(case)
    nodes=[{k:n[k] for k in ('id','kind','label','inputs','operator','fact_id','code_line') if k in n} for n in graph['nodes']]
    target=spec['target'];fact=program['facts'][target];ids=[n['id'] for n in graph['nodes'] if n.get('fact_id')==target];a,b=spec['anchor']
    separator='\n' if '|' in c[a:b] else ' '
    instructions=['Preserve the question and all original content outside the exact edit slots.',
                  'The financial object and period are those specified below, not an assumed bank or quarter.',
                  'Do not disclose conditional answers, graph IDs, labels or construction metadata.']
    if axis=='IC_VALUE':
        pos=a if plan['perturb_position']=='before' else b
        allowed=[str(spec['alternative'])]
        instructions.append('Selected quantity: '+json.dumps({'fact_id':target,'original_evidence':fact,'new_value':spec['alternative']},ensure_ascii=False))
        slots=[slot(pos,pos,'',ids,'VALUE','Independently write one standalone conflicting value claim for the selected quantity and new value.'+
                    ' Preserve the specified quantity/entity/period/unit. Keep all numbers in digits. No attribution or correction. '+
                    (('End' if pos==a else 'Begin')+' with '+('a newline.' if separator=='\n' else 'a space.')),allowed=allowed)]
    elif axis=='IC_SOURCE':
        request_from_value = __import__('finarch.dataset.02-generation.01-perturbation.source_from_value', fromlist=['request_from_value']).request_from_value
        request,_=request_from_value(case,variant,sample,program,nodes,fact)
        validate('02-generation.02-generate-text.realization.request',request)
        return request
    elif axis=='IC_RELATION':
        r=spec['relation'];ids=plan['branches']['B']['relation_node_ids']
        nodes += [{k:n[k] for k in ('id','kind','label','inputs','operator','fact_id','code_line') if k in n} for n in plan['graphs']['B']['nodes'] if n['id'] in ids]
        instructions.append('Selected operation and scope: '+json.dumps(plan['relation']['properties'],ensure_ascii=False))
        scoped={d['fact_id']:d for d in relation_scope.descriptors(c,program)[0]}
        relation,instruction,allowed=relation_scope.contract(scoped[r['target']],scoped[r['operand']],r['factor'])
        instructions.append('Relation identities and numeric scope: '+json.dumps(relation,ensure_ascii=False))
        slots=[slot(b,b,'',ids,'RELATION',instruction,allowed=allowed)]
    else:
        key=plan['fact_id'];f=program['facts'][key];e=spec['ea'][key];start,end=e['span']
        ids=preview['graph_binding']['missing_node_ids'];tagged=preview['intermediate']['context']
        remain=numbers(c[start:end]);remain.subtract(numbers(f['text']));remain=+remain
        allowed=[str(n) for n,count in remain.items() for _ in range(count)]
        intent='Remove the selected amount, retaining its category and ALL other numbers and their original meanings. Smooth only this sentence. Do not signal missing, unknown, removed or unreported information. '
        if e.get('table'):intent='Leave this table amount cell empty; preserve the row/column and other cells.'
        slots=[slot(start,end,c[start:end],ids,'EA',intent,allowed=allowed)]
        instructions.append('Target identity: '+key.replace('_',' ')+'. Same digits for OTHER periods/quantities must remain. Selected source quote: '+f['text'])
    request={'context':c,'question':sample['question'],'axis':axis,'python_code':program['code'],
             'graph_structure':nodes,'edit_slots':slots,'instructions':instructions,'tagged_context':tagged}
    validate('02-generation.02-generate-text.realization.request',request)
    return request
