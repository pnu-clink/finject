"""Opt-in bounded coefficient selection, fixed targets and no provider calls."""
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import re

NAME='bounded-coefficients-v1'
CANDIDATES={'VALUE':['0.9','1.1'],'RELATION':['0.5','2']}

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

def validate(policy):
    if policy is None or policy=={'name':'legacy-v1'}:return None
    if not isinstance(policy,dict) or set(policy)!={'name','seed'} or policy['name']!=NAME or type(policy['seed']) is not int:
        raise ValueError('INVALID_PERTURBATION_POLICY')
    return deepcopy(policy)


def bind(settings,bundle,*,resume=False):
    """Use the v2 loader, reject changed policy before writing any runtime config."""
    load_run = __import__('finarch.dataset.90-operations.schedule_settings', fromlist=['load_run']).load_run
    policy=validate(load_run('generation',settings.get('hyperparameter_path')).get('perturbation_policy'))
    path=Path(bundle)/'02-generation/perturbation-policy.json'
    state={'policy':policy,'policy_sha256':digest(policy)}
    if path.exists():
        if json.loads(path.read_text())!=state:raise ValueError('PERTURBATION_POLICY_SNAPSHOT_MISMATCH')
    elif policy:
        if resume or any((Path(bundle)/'02-generation').glob('*-round')):
            raise ValueError('OPT_IN_REQUIRES_NEW_GENERATION_RUN')
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(state,indent=2)+'\n')
    result=deepcopy(settings)
    if policy:result['perturbation_policy']=policy
    else:result.pop('perturbation_policy',None)
    return result


class NoCoefficient(ValueError):
    def __init__(self,report):
        self.report=report
        super().__init__('NO_ADMISSIBLE_COEFFICIENT')


def precision(sample):
    question=sample['question'].lower()
    places={'one':1,'two':2,'three':3,'four':4,'0':0,'1':1,'2':2,'3':3,'4':4}
    if 'nearest integer' in question or 'nearest whole number' in question:digits=0
    else:
        match=re.search(r'\b(one|two|three|four|[0-4]) decimal places?\b',question)
        if not match:raise ValueError('QUESTION_PRECISION_UNKNOWN')
        digits=places[match[1]]
    if sample.get('reference_precision')!=digits:raise ValueError('QUESTION_REFERENCE_PRECISION_MISMATCH')
    return digits


def domain(fact,value):
    """A deliberately small numeric-unit grammar, not a complete semantic domain solver."""
    unit=(fact.get('unit') or '').lower().strip()
    if not value.is_finite():raise ValueError('NONFINITE_ALTERNATIVE')
    if unit in ('usd','eur','gbp','dollars','$'):
        original=Decimal(str(fact['value']).replace(',',''))
        if original*value<0:raise ValueError('SIGN_DOMAIN_VIOLATION')
    elif unit in ('count','shares','employees','people','units'):
        if value<0 or value!=value.to_integral_value():raise ValueError('INTEGER_COUNT_DOMAIN_VIOLATION')
    elif unit in ('percent','%'):
        if not 0<=value<=100:raise ValueError('PERCENT_BOUND_VIOLATION')
    else:raise ValueError('UNIT_DOMAIN_UNKNOWN')


def binding(sample,program,policy,family):
    policy=validate(policy)
    return {'policy':policy,'policy_sha256':digest(policy),'input_sha256':digest({'question':sample['question'],'context':sample['context'],'program':program,
            'precision':sample.get('reference_precision'),'reference_type':sample.get('reference_answer_type')}),
            'case_id':sample['id'],'family':family}


def select(sample,program,original,fact,value,family,policy,attempt,inherited=None):
    """Try at most two fixed-target factors, retaining every rejection and graph check."""
    identity=binding(sample,program,policy,family)
    ordered=sorted(CANDIDATES[family],key=lambda factor:digest({**identity,'factor':factor}))
    report={**identity,'rubric_version':'bounded-domain-and-explicit-precision-v1','ordered_candidates':ordered,
            'target_order':'UNCHANGED_SOURCE_ORDER','attempts':[],'selected_factor':None,'status':'NOT_EVALUATED'}
    if inherited:
        if any(inherited.get(k)!=v for k,v in identity.items()):raise ValueError('INHERITED_COEFFICIENT_BINDING_MISMATCH')
        if inherited.get('selected_factor') not in ordered:raise ValueError('INHERITED_COEFFICIENT_MISSING')
        ordered=[inherited['selected_factor']];report['inherited_selection_sha256']=digest(inherited)
    for factor in ordered:
        trial={'factor':factor,'status':'REJECTED'}
        try:
            digits=precision(sample)
            alternative=value*Decimal(factor)
            if alternative==value and family=='VALUE':raise ValueError('UNCHANGED_TARGET_VALUE')
            if value==0 and family=='RELATION':raise ValueError('ZERO_COEFFICIENT_INPUT')
            domain(fact,alternative)
            branch,graph,execution=attempt(factor,format(alternative,'f'))
            before=Decimal(next(n['computed'] for n in original['nodes'] if n['id']==original['output']))
            after=Decimal(execution['exact_value'])
            if before==after:raise ValueError('EXACT_ANSWER_UNCHANGED')
            from finarch.shared.reference import Reference, normalize
            ref=Reference(**{k:sample[k] for k in ('reference_answer','reference_answer_type','reference_precision')})
            if normalize(str(before),ref)==normalize(str(after),ref):raise ValueError('REFERENCE_DISPLAY_UNCHANGED')
            quantum=Decimal(1).scaleb(-digits)
            if before.quantize(quantum,rounding=ROUND_HALF_UP)==after.quantize(quantum,rounding=ROUND_HALF_UP):
                raise ValueError('DISPLAYED_ANSWER_UNCHANGED')
            trial.update(status='SELECTED',original_answer=str(before),changed_answer=str(after),question_precision=digits)
            report['attempts'].append(trial);report.update(status='SELECTED',selected_factor=factor)
            return branch,graph,execution,format(alternative,'f'),report
        except ValueError as error:
            trial['reason']=str(error);report['attempts'].append(trial)
    raise NoCoefficient(report)
