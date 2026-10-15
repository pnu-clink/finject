"""Resolve external evidence from a reviewed local catalog, never model assertions."""
import ast
import hashlib
import json
from pathlib import Path

CATALOG=(Path(__file__).resolve().parent / '../../../../..').resolve()/'config/external-evidence.json'


def resolve(program):
    declarations=program.get('external_evidence',[])
    calls=[n for n in ast.walk(ast.parse(program['code'])) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='evidence']
    used=set()
    for call in calls:
        if not call.args or not isinstance(call.args[0],ast.Constant) or not isinstance(call.args[0].value,str):
            raise ValueError('INVALID_EVIDENCE_CALL')
        used.add(call.args[0].value)
    if not declarations and not used:return {}
    catalog=json.loads(CATALOG.read_text())['entries'];resolved={}
    for d in declarations:
        key=d['id']
        if key in resolved:raise ValueError('DUPLICATE_EXTERNAL_EVIDENCE')
        if key not in catalog:raise ValueError('UNVERIFIED_EXTERNAL_EVIDENCE:'+key)
        entry=catalog[key]
        if entry.get('source_status')!='VERIFIED':raise ValueError('UNVERIFIED_EXTERNAL_EVIDENCE:'+key)
        if 'source_url' in d and d['source_url']!=entry['url']:raise ValueError('EVIDENCE_SOURCE_MISMATCH')
        if not d.get('application_note','').strip():raise ValueError('EVIDENCE_APPLICATION_NOTE_REQUIRED')
        resolved[key]={**entry,'id':key,'application_note':d['application_note'],
            'model_claim':d,
            'application_status':'REQUIRES_REVIEW',
            'catalog_entry_sha256':hashlib.sha256(json.dumps(entry,sort_keys=True).encode()).hexdigest()}
    if used!=set(resolved):raise ValueError('EVIDENCE_DECLARATION_CALL_MISMATCH')
    return resolved


def lookup(entry,args):
    if len(args)!=len(entry['selectors']):raise ValueError('EVIDENCE_SELECTOR_ARITY')
    matches=[r for r in entry['rows'] if r['keys']==list(args)]
    if len(matches)!=1:raise ValueError('EVIDENCE_SELECTION_NOT_SUPPORTED')
    return float(matches[0]['value'])


def publish(ctx,program):
    records=resolve(program)
    if records:
        ctx.save('03-calculation/02-prepare-code/external-evidence.json',
                 {'status':'SOURCE_VERIFIED','application_status':'REQUIRES_REVIEW','records':records})
        ctx.save_text('03-calculation/02-prepare-code/EXTERNAL-EVIDENCE-README.md',
                      ((Path(__file__).resolve().parent / '../../..').resolve() / 'dataset/02-generation/03-validation/external-evidence-readme.md').read_text())
    return records
