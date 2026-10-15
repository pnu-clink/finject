"""Build graph branches and edit contracts from approved preparation data."""
import ast
from copy import deepcopy
from decimal import Decimal
import json

slot = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['slot']).slot
numbers = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['numbers']).numbers
boundaries = __import__('finarch.dataset.02-generation.01-perturbation.production_plan', fromlist=['boundaries']).boundaries
branch_program = __import__('finarch.dataset.02-generation.01-perturbation.value_plan', fromlist=['branch_program']).branch_program
missing_graph = __import__('finarch.dataset.02-generation.01-perturbation.ea_plan', fromlist=['build']).build
from finarch.dataset.shared.calculation.python_graph import compile_graph
from finarch.dataset.shared.calculation.python_runtime import execute
from finarch.dataset.shared.calculation.number_normalization import load_rules, normalize_number
from finarch.shared.reference import Reference, normalize
relation_scope = __import__('finarch.dataset.02-generation.01-perturbation.relation_scope', fromlist=['*'])
RELATION_PLACEMENT_VERSION = 'table-after-paragraph-v1'

TYPES = (
 ('01-ic-value-before', 'IC_VALUE', 'IC_VALUE_01_BEFORE'),
 ('02-ic-value-after', 'IC_VALUE', 'IC_VALUE_01_AFTER'),
 ('03-ic-source-type-1', 'IC_SOURCE', 'IC_SOURCE_A_ONLY'),
 ('04-ic-source-type-2', 'IC_SOURCE', 'IC_SOURCE_B_ONLY'),
 ('05-ic-relation', 'IC_RELATION', 'IC_RELATION_01'),
 ('06-ea-earlier-input', 'EA', 'EA_01'),
 ('07-ea-later-input', 'EA', 'EA_02'))


def checked_branch(program):
    result = execute(program)
    if result.status != 'PASS':
        raise ValueError('BRANCH_EXECUTION_FAILED:' + result.reason)
    graph, value, _ = compile_graph(program)
    values = {n['id']: n.get('computed') for n in graph['nodes']}
    if str(value) != result.data['exact_value'] or any(values[node] != result.data['trace'].get(name) for name,node in graph['variables'].items()):
        raise ValueError('BRANCH_GRAPH_EXECUTION_MISMATCH')
    return graph, result.data


def relation_branch(program, context, target, operand, factor="2"):
    tree = ast.parse(program['code']); bindings = {}; last = -1
    for i,node in enumerate(tree.body):
        if isinstance(node,ast.Assign) and isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Name) and node.value.func.id=='fact':
            bindings[node.value.args[0].value]=node.targets[0].id;last=i
    if set(bindings)!=set(program['facts']):raise ValueError('RELATION_BINDING_INCOMPLETE')
    replacement='perturbed_'+bindings[target]
    names={n.id for n in ast.walk(tree) if isinstance(n,ast.Name)}
    if replacement in names:raise ValueError('RELATION_NAME_COLLISION')
    class Replace(ast.NodeTransformer):
        def visit_Name(self,node):
            return ast.copy_location(ast.Name(id=replacement,ctx=node.ctx),node) if isinstance(node.ctx,ast.Load) and node.id==bindings[target] else node
    prefix=[ast.unparse(n) for n in tree.body[:last+1] if not (isinstance(n,ast.Assign) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='fact' and n.value.args[0].value==target and target!=operand)]
    branch=deepcopy(program)
    if target!=operand:del branch['facts'][target]
    branch.update(context=context,code='\n'.join(prefix+[replacement+' = '+bindings[operand]+' * '+factor]+[ast.unparse(Replace().visit(n)) for n in tree.body[last+1:]]))
    return branch


def value_boundaries(context, span):
    """Keep a contiguous Markdown table intact when placing a value claim."""
    start, end = boundaries(context, span)
    if '|' not in context[start:end]:
        return start, end
    while start > 0:
        previous = context.rfind('\n', 0, start - 1) + 1
        if '|' not in context[previous:start - 1]:
            break
        start = previous
    while end < len(context):
        following = context.find('\n', end + 1)
        if following < 0:
            following = len(context)
        if '|' not in context[end + 1:following]:
            break
        end = following
    return start, end


def build(sample, program, original, index, policy=None, perturbation_policy=None, inherited_selection=None):
    validate = __import__('finarch.dataset.90-operations.perturbation_policy', fromlist=['validate']).validate
    select = __import__('finarch.dataset.90-operations.perturbation_policy', fromlist=['select']).select
    perturbation_policy=validate(perturbation_policy)
    folder,axis,label=TYPES[index];context=sample['context']
    ordered=sorted(program['facts'],key=lambda k:program['facts'][k]['span'][0])
    if not ordered:raise ValueError('NO_SOURCE_FACTS')
    target=ordered[0] if index<5 else ordered[index-5] if len(ordered)>index-5 else None
    if target is None:raise ValueError('MISSING_SECOND_EA_INPUT')
    fact=program['facts'][target];start,end=boundaries(context,fact['span'])
    while start<end and context[start].isspace():start+=1
    while end>start and context[end-1].isspace():end-=1
    ids=[n['id'] for n in original['nodes'] if n.get('fact_id')==target]
    if not ids:raise ValueError('FACT_GRAPH_MAPPING_MISSING')
    nodes=[{k:n[k] for k in ('id','kind','label','inputs','operator','fact_id','code_line') if k in n} for n in original['nodes']]
    intent={'preserve_question':True,'preserve_other_evidence':True,'target':target,'target_original':fact}
    instructions=['Preserve the question and source content outside the authorized edit slots. Write only the requested edit. Preserve the quantity, entity, period and unit. Do not expose construction metadata or computed answers.']
    request={'context':context,'question':sample['question'],'axis':axis,'python_code':program['code'],'graph_structure':nodes,'tagged_context':None,'instructions':instructions}
    plan={'folder':folder,'label':label,'axis':axis,'target':target,'anchor':[start,end],'original_graph':original,'selection':'First source-ordered input; EA uses the first and second source-ordered inputs.'}
    ref=Reference(**{k:sample[k] for k in ('reference_answer','reference_answer_type','reference_precision')})
    if index<4:
        rules,rules_hash=load_rules();steps=[]
        numeric,applied=normalize_number(str(fact['value']),rules,steps)
        value=Decimal(numeric);alternative=str(value*Decimal('1.1') if value else Decimal(1))
        plan['number_normalization']={'original':str(fact['value']),'normalized':numeric,'rules_sha256':rules_hash,'applied_rules':applied,'steps':steps}
        if perturbation_policy:
            def attempt(factor, alternative):
                branch=branch_program(program,context,target,alternative)
                graph,execution=checked_branch(branch)
                return branch,graph,execution
            branch,graph,execution,alternative,selection=select(sample,program,original,fact,value,'VALUE',perturbation_policy,attempt,inherited_selection)
            plan['coefficient_selection']=selection
        else:
            branch=branch_program(program,context,target,alternative);graph,execution=checked_branch(branch)
        original_value=next(n['computed'] for n in original['nodes'] if n['id']==original['output'])
        if normalize(original_value,ref)==normalize(execution['exact_value'],ref):raise ValueError('FINAL_ANSWER_UNCHANGED')
        plan.update(graph=graph,execution=execution,alternative=alternative,program=branch)
        intent.update(value_pair=[fact['value'],alternative],perturb_position='before' if index in (0,2) else 'after')
        start,end=value_boundaries(context,fact['span'])
        plan['anchor']=[start,end]
        pos=start if index in (0,2) else end;separator='\n' if '|' in context[start:end] else ' '
        instructions.append('Insert the conflicting sentence outside the entire table, before its header or after its final row. Never insert prose inside a table row or cell.')
        request['edit_slots']=[slot(pos,pos,'',ids,'VALUE','Write one standalone conflicting value sentence. Keep all numbers in digits. '+('End' if index==0 else 'Begin')+' with '+('a newline.' if separator=='\n' else 'a space.'),allowed=[alternative])]
        instructions.append('Selected quantity: '+json.dumps({'evidence':fact,'alternative':alternative}))
    elif axis=='IC_RELATION':
        pairs,cells=relation_scope.candidates(context,program);trials=[]
        original_value=next(n['computed'] for n in original['nodes'] if n['id']==original['output'])
        coefficient_failure=None
        for left,right in pairs:
            target=left['fact_id'];operand=right['fact_id'];fact=left['fact'];factor='2'
            trial={'target':target,'operand':operand,'target_period':left['period'],'operand_period':right['period']}
            try:
                expanded=relation_scope.add_reference(program,right)
                if perturbation_policy:
                    def attempt(factor, alternative):
                        relation_scope.check_structure(left,right,factor,cells)
                        branch=relation_branch(expanded,context,target,operand,factor)
                        graph,execution=checked_branch(branch)
                        return branch,graph,execution
                    branch,graph,execution,_,selection=select(sample,program,original,fact,relation_scope.fact_decimal(right['fact']['value']),'RELATION',perturbation_policy,attempt)
                    factor=selection['selected_factor']
                else:
                    relation_scope.check_structure(left,right,factor,cells)
                    branch=relation_branch(expanded,context,target,operand,factor)
                    graph,execution=checked_branch(branch)
                if normalize(original_value,ref)==normalize(execution['exact_value'],ref):raise ValueError('RELATION_ANSWER_UNCHANGED')
                trial['status']='SELECTED';trials.append(trial)
                break
            except ValueError as error:
                if hasattr(error,'report'):coefficient_failure=error
                trials.append({**trial,'status':'REJECTED','reason':str(error)})
        else:
            if coefficient_failure is not None:raise coefficient_failure
            raise ValueError('NO_SOURCE_SCOPED_RELATION:'+json.dumps(trials))
        start,end=value_boundaries(context,fact['span'])
        table = '|' in context[start:end]
        ids=[n['id'] for n in original['nodes'] if n.get('fact_id')==target]
        if not ids:raise ValueError('FACT_GRAPH_MAPPING_MISSING')
        plan.update(target=target,anchor=[start,end],relation_policy_version=relation_scope.VERSION,
                    relation_placement_version=RELATION_PLACEMENT_VERSION,
                    selection={'method':relation_scope.VERSION,'cross_period_preferred':True,'candidate_limit':relation_scope.LIMIT,
                               'attempts':trials,'additional_facts':{k:v for k,v in expanded['facts'].items() if k not in program['facts']}})
        if perturbation_policy:plan['coefficient_selection']=selection
        rules,rules_hash=load_rules();numeric_facts={}
        for role,descriptor in (('target',left),('operand',right)):
            steps=[];raw=str(descriptor['fact']['value'])
            normalized,applied=normalize_number(raw,rules,steps)
            numeric_facts[role]={'original':raw,'normalized':normalized,'applied_rules':applied,'steps':steps}
        plan['number_normalization']={'rules_sha256':rules_hash,'facts':numeric_facts}
        relation,instruction,allowed=relation_scope.contract(left,right,factor)
        prefix = '\n\n' if table else ''
        if table:
            instruction = instruction.replace('Begin with a space', 'Begin with two newline characters')
            instruction += ' Place the relation in a separate paragraph after the entire table, never inside a row or cell.'
            if end < len(context):
                instruction += ' End with a newline to separate any following source text.'
        intent.update(target=target,target_original=fact)
        plan.update(graph=graph,execution=execution,program=branch);intent.update(relation=relation,preserve_original_values=True)
        instructions.append('Express this conflicting operation without computing its result: '+json.dumps(relation))
        request['edit_slots']=[slot(end,end,'',ids,'RELATION',instruction,prefix=prefix,allowed=allowed)]
    else:
        if numbers(fact['text']) & numbers(sample['question']):raise ValueError('EA_VALUE_PRESENT_IN_QUESTION')
        graph,binding,_=missing_graph({**program,'context':context},target);plan.update(graph=graph,execution=binding,program=binding)
        if '|' in context[start:end]:
            start,end=fact['span']
            if start and context[start-1]=='$':start-=1
            wording='Leave only this table amount cell empty. Preserve every other cell.'
        else:wording='Remove the selected amount while preserving its category and all other numeric evidence. Do not describe it as missing or removed.'
        remaining=numbers(context[start:end]);remaining.subtract(numbers(fact['text']));remaining=+remaining
        request['edit_slots']=[slot(start,end,context[start:end],ids,'EA',wording,allowed=[str(n) for n,count in remaining.items() for _ in range(count)])]
        intent.update(deletion={'span':[start,end],'before':context[start:end],'fact_id':target},scope='Remove the selected source input value.')
    plan['intent']=intent;plan['request']=request
    if axis == 'EA':
        inversion = __import__('finarch.dataset.02-generation.01-perturbation.ea_inversion', fromlist=['recovery_inputs'])
        plan['recovery_inputs'] = inversion.recovery_inputs(program, target)
    if axis == 'EA' and policy and policy.get('enabled') is True:
        ea = __import__('finarch.dataset.02-generation.01-perturbation.ea_plan', fromlist=['screen_recovery'])
        descriptor = ea.recovery_descriptor(context, fact['span'], target)
        # Only the selected value is erased for this private planning preview.
        left, right = fact['span']
        preview = {'context': context[:left] + context[right:], 'question': sample['question']}
        plan['recovery_target_descriptor'] = descriptor
        plan['recovery_preview'] = ea.screen_recovery(preview, descriptor, policy)
    return plan


def source_request(plan, base):
    if base.get('status')!='PASS':raise ValueError('AUDITED_VALUE_DEPENDENCY_REQUIRED')
    request=deepcopy(plan['request']);patch=base['patches'][0];after=plan['label']=='IC_SOURCE_B_ONLY'
    if patch['start']!=patch['end']:raise ValueError('VALUE_INSERTION_REQUIRED')
    context=base['observation']['context']
    if after:
        position=patch['start']+len(patch['text'].rstrip())-1
        if context[position:position+1]!='.':raise ValueError('VALUE_SENTENCE_TERMINATOR_REQUIRED')
    else:
        target=plan['intent']['target_original']['span']
        shift=len(patch['text'])
        original=plan['request']['context']
        start,end=boundaries(original,target)
        if '|' in original[start:end]:
            position=target[1]+shift
        else:
            # Attach before the next clause delimiter, not after later claims.
            import re
            tail=original[target[1]:end]
            delimiter=re.search(r'[,;.!?](?=\s|$)',tail)
            claim_end=target[1]+delimiter.start() if delimiter else end
            position=claim_end+shift
            if not delimiter and context[position-1:position] in ('.','!','?'):position-=1
    side='B' if after else 'A'
    source={'side':side,'role':'financial analyst','information_access':'direct access to underlying transaction records','verification':'checked the reported amount against the underlying records','intended_reliability':'H'}
    request.update(context=base['observation']['context'],axis='IC_SOURCE',instructions=[
        'Preserve both existing value claims, every number, and the question verbatim. Insert one parenthesized attribution inside the assigned claim, before its existing clause or sentence punctuation. Never append attribution after the sentence terminator. For a table claim, attach the parentheses to the assigned value inside the same cell.',
        'Assigned source: '+json.dumps(source), 'Attribute the '+('later added claim' if after else 'later original claim')+' only. Do not add a source to the other claim.'])
    request['edit_slots']=[slot(position,position,'',patch['element_ids'],'SOURCE_'+side,'Insert a leading space followed by one parenthesized source attribution, for example (according to the financial analyst who verified the underlying records). Do not include a sentence-ending period or change existing punctuation.')]
    plan['intent'].update(source_condition=side+'_ONLY',sources=[source],base_variant='IC_VALUE_01_AFTER' if after else 'IC_VALUE_01_BEFORE',source_assignment_by_value=[{'side':s,'value':plan['intent']['value_pair'][i],'source':source if s==side else None} for i,s in enumerate(('A','B'))])
    return request
