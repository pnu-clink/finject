"""A round reads the cumulative supplements once; every actual call snapshots them."""
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import json
from finarch.shared.providers.roles import resolve_role

_ACTIVE = ContextVar('feedback_supplements', default={})

@contextmanager
def use_feedback(directory, *, case=None, target_round=None):
    parts={}
    if directory.exists():
        for path in directory.glob('*/*.json'):
            item=json.loads(path.read_text())
            if item.get('feedback_refs'):
                load = __import__('finarch.dataset.90-operations.feedback_records', fromlist=['load']).load
                for ref in item['feedback_refs']:
                    record=load(ref,case=case,target_round=target_round)
                    key=(resolve_role(record['target_role']),record['axis'])
                    parts.setdefault(key,[]).append({**record,'file':ref['path'],'feedback_ref':ref})
                continue
            if item.get('guidance'):
                if case is not None and item.get('case') not in (None,case):raise ValueError('FEEDBACK_CASE_MISMATCH')
                parts.setdefault((resolve_role(item['target_role']),item['axis']),[]).append({**item,'file':str(path)})
    token=_ACTIVE.set(parts)
    try: yield
    finally: _ACTIVE.reset(token)

def supplement(role, axis, definition):
    items=_ACTIVE.get().get((resolve_role(role),axis))
    if not items:return definition
    result=dict(definition)
    result['parts']=[*definition.get('parts',[])]
    result['instruction']=definition['instruction']
    for item in items:
        text=item['guidance']
        result['parts'].append({'file':item['file'],'version':item['version'],
          'text':text,'sha256':hashlib.sha256(text.encode()).hexdigest(),
          'scope':'case retry feedback' if item.get('feedback_ref') else 'cumulative failure guidance',
          **({'feedback_ref':item['feedback_ref']} if item.get('feedback_ref') else {})})
        result['instruction']+='\n\n'+text
    result['sha256']=hashlib.sha256(result['instruction'].encode()).hexdigest()
    return result
