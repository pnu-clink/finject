resolve_read = __import__('finarch.dataset.90-operations.ordered_artifacts', fromlist=['resolve_read']).resolve_read
variant_root = __import__('finarch.dataset.90-operations.stage_paths', fromlist=['variant_root']).variant_root
"""Create two private source plans sharing the verified IC-value calculation."""
import argparse
import hashlib
import json
from pathlib import Path
RunContext = __import__('finarch.dataset.90-operations.staging', fromlist=['RunContext']).RunContext
from finarch.dataset.shared.calculation.python_graph import load_graph
from finarch.dataset.schemas.source_plan import SourcePlan

RULES=[
 'Resolve base_plan_ref for the fixed A/B values, target fact, unit and two conditional answers. Do not change them.',
 'Keep the original question, calculation code and applicable entity/period/quantity/unit unchanged.',
 'Preserve both value claims. Keep the claim order of the assigned audited IC-VALUE input. Attribute only the assigned claim to its specified source; leave the other claim without any source mention; do not present B as extra income or a correction of A.',
 'Express the assigned source role, information access and verification. Never describe the unattributed claim as low-trust, unverified, anonymous or second-hand.',
 'Do not expose A_ONLY/B_ONLY or intended_reliability as labels in the final context.',
 'Higher intended reliability is not proof of truth. Do not insert a definitive winner or a common CONFLICT answer.',
 'These source conditions are synthetic perturbation material, not claims found in the original report.'
]


def make_plan(base_ref,digest,condition):
    if condition not in ('A_ONLY','B_ONLY'):raise ValueError('UNKNOWN_SOURCE_CONDITION')
    side=condition[0]
    sources=[{'side':side,'source_id':'trusted_reporter','role':'financial analyst',
      'information_access':'direct access to the underlying transaction records',
      'verification':'checked the reported amount against the underlying transaction records',
      'attribution':'direct','intended_reliability':'H'}]
    return SourcePlan.model_validate({'axis':'IC_SOURCE','base_plan_ref':base_ref,'base_plan_sha256':digest,'source_condition':condition,
       'base_variant':'IC_VALUE_01_BEFORE' if side=='A' else 'IC_VALUE_01_AFTER',
       'claim_order':['B','A'] if side=='A' else ['A','B'],'sources':sources,'realization_rules':RULES,
       'provenance':'locally_authored_source_conditions_not_original_facts','semantic_status':'NOT_EVALUATED','final_text_status':'NOT_RUN','model_calls':0},strict=True).model_dump()


def check_base(base):
    if base.get('axis')!='IC_VALUE' or not all(base.get('checks',{}).get(k) is True for k in ['same_code','original_preserved','python_graph_equal','different_final_answers']):raise ValueError('VALUE_CALCULATION_NOT_VERIFIED')
    if base['answers']['A']['computed']==base['answers']['B']['computed']:raise ValueError('VALUE_ANSWERS_IDENTICAL')


def create(case_dir,base_label='IC_VALUE_01'):
    # [SP01] docs/02-architecture.md#SP01 — fixed A/B graph references plus source-only metadata.
    if Path(base_label).name!=base_label:raise ValueError('INVALID_BASE_LABEL')
    case=Path(case_dir).resolve();root=case/'04-perturbation/02-plan-ic-source/01-read-value-pair'
    if root.exists():raise ValueError('SOURCE_FAMILY_ALREADY_EXISTS')
    ctx=RunContext.resume(case,{},case.name)
    with ctx.trace.activate(),ctx.trace.span('source_plan.create',stage='04-perturbation/02-plan-ic-source',step='01-read-value-pair') as outcome:
        ctx.save('04-perturbation/02-plan-ic-source/01-read-value-pair/start.json',{'base_label':base_label,'conditions':['A_ONLY','B_ONLY'],'model_calls':0})
        try:
            load_graph(case)
            relative=f'{variant_root(base_label)}/04-plan.json';raw=resolve_read(case/relative).read_bytes();base=json.loads(raw);check_base(base)
            digest=hashlib.sha256(raw).hexdigest();index=case/'04-perturbation/05-list-candidates/03-result.json';index.parent.mkdir(parents=True,exist_ok=True);existing=json.loads(index.read_text())
            variants=[]
            for condition in ['A_ONLY','B_ONLY']:
                plan=make_plan(relative,digest,condition);label='IC_SOURCE_'+condition;path=f'{variant_root(label)}'
                ctx.save(path+'/plan.json',plan)
                ctx.save(path+'/validation.json',{'status':'PASS','scope':'source plan schema and fixed mapping only; not final prose or semantic validity','base_hash_verified':True,'graph_copied':False})
                ctx.save_text(path+'/README.md','# Source conditions plan 13\n\nplan.json contains the routes, explanations of the fixed A/B plan, and the role, access to information, and verification of the sources attached to each claim. The original source is not true, but a condition for production. The graph and the numbers are not copied by reference to base_plan_ref. A_ONLY only applies the original A of the IC-VALUE text before, and B_ONLY applies the source only to the additional B of the text after IC-VALLUE. The other side does not add a source description. The LLM call; the latest sentence creation; the US test has not yet been performed. validation.json is a formatting and event correction test. 4You can choose two conditions from the bar.\n')
                variants.append({'label':label,'axis':'IC_SOURCE','source_condition':condition,'status':'NOT_EVALUATED','plan_status':'PASS','plan':plan,'reason':'Source-assignment plan saved; generated text and final semantics not evaluated'})
            if set(v['label'] for v in existing)&set(v['label'] for v in variants):raise ValueError('SOURCE_LABEL_ALREADY_EXISTS')
            ctx.save('04-perturbation/02-plan-ic-source/01-read-value-pair/previous-variants.json',existing)
            active=[v for v in existing if v.get('axis')!='IC_SOURCE']
            tmp=index.with_suffix('.tmp');tmp.write_text(json.dumps(active+variants,ensure_ascii=False,indent=2)+'\n');tmp.replace(index);ctx.trace.artifact('04-perturbation/05-list-candidates/03-result.json')
            ctx.save('04-perturbation/02-plan-ic-source/01-read-value-pair/result.json',{'status':'PASS','scope':'two source plans only','base_plan_ref':relative,'base_plan_sha256':digest,'conditions':[v['source_condition'] for v in variants],'model_calls':0})
            outcome.update(status='PASS',reason='TWO_SOURCE_PLANS_SAVED')
            return {'case':case.name,'plans':2,'model_calls':0,'final_text':'NOT_RUN'}
        except Exception as error:
            ctx.save('04-perturbation/02-plan-ic-source/01-read-value-pair/03-result/failure.json',{'status':'FAIL','reason':str(error)});outcome.update(status='FAIL',reason=str(error));raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--case',required=True);args=p.parse_args();print(json.dumps(create(args.case),ensure_ascii=False))
