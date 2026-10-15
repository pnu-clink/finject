"""Prepare original Q/C only; never execute a baseline or import its runner."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from collections import Counter
InputSnapshot = __import__('finarch.dataset.03-release.response_screen', fromlist=['InputSnapshot']).InputSnapshot
PROJECT = __import__('finarch.dataset.03-release.response_screen', fromlist=['PROJECT']).PROJECT
from finarch.dataset.schemas.original_baseline import PublicOriginal, BaselineRecord, BaselineReport


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def group_frozen(rows):
    groups = {}; seen = set()
    for row in rows:
        identifier = row['id']
        if identifier in seen:
            raise ValueError('DUPLICATE_VARIANT')
        seen.add(identifier)
        if not re.fullmatch(r'test-\d{4}/\d{2}-[a-z0-9-]+', identifier):
            raise ValueError('INVALID_VARIANT_PARENT')
        parent = identifier.split('/')[0]
        groups.setdefault(parent, []).append(identifier)
    return groups


def approved_directory(source, parent, approval):
    expected = Path('01-preparation') / parent
    if approval.get('case_path') != expected.as_posix():
        raise ValueError('WRONG_APPROVED_PARENT')
    base = (source / expected).resolve()
    if not base.is_relative_to(source.resolve()):
        raise ValueError('APPROVED_PATH_ESCAPE')
    relative = approval.get('files', {}).get('working_input', {}).get('path', '')
    if not re.fullmatch(r'\d{2}-round/data.json', relative):
        raise ValueError('MISSING_OR_INVALID_APPROVED_ROUND')
    return base, relative.split('/')[0]


def public_original(data, parent):
    if data.get('id') != parent:
        raise ValueError('ORIGINAL_PARENT_MISMATCH')
    return PublicOriginal.model_validate({k: data[k] for k in ('id', 'context', 'question')}).model_dump()


def settings(request):
    allowed = {'model','temperature','max_tokens','messages','response_format'}
    if not isinstance(request, dict) or set(request) != allowed:
        raise ValueError('REQUEST_FIELDS_CHANGED')
    messages = request['messages']
    if len(messages) != 2 or [m.get('role') for m in messages] != ['system','user'] or any(set(m) != {'role','content'} for m in messages):
        raise ValueError('REQUEST_MESSAGES_CHANGED')
    expected_system = 'Answer the question using the provided context. If conflicting information prevents a unique answer, explain the conflict. If necessary information is missing, state what is missing. Provide your final answer clearly.'
    if messages[0]['content'] != expected_system:
        raise ValueError('SYSTEM_PROMPT_CHANGED')
    schema = {'type':'object','properties':{'answer':{'type':'string'}},'required':['answer'],'additionalProperties':False}
    expected = {'type':'json_schema','json_schema':{'name':'answer','strict':True,'schema':schema}}
    if request['response_format'] != expected or request['temperature'] != 0 or request['max_tokens'] != 4096:
        raise ValueError('REQUEST_CONDITIONS_CHANGED')
    return {k: deepcopy(v) for k,v in request.items() if k != 'messages'} | {'system': messages[0]['content']}


def make_request(original, template):
    public = PublicOriginal.model_validate(original).model_dump()
    config = settings(template)
    request = {k:v for k,v in config.items() if k != 'system'}
    request['messages'] = [{'role':'system','content':config['system']},
        {'role':'user','content':'Question:\n'+public['question']+'\n\nContext:\n'+public['context']}]
    return request


def build(source, output, quality_root, *, project=PROJECT, expected_originals=92, expected_variants=624):
    source, output, quality_root, project = [Path(p).resolve() for p in (source, output, quality_root, project)]
    for protected in (source, quality_root):
        if output.is_relative_to(protected) or protected.is_relative_to(output):
            raise ValueError('OUTPUT_MUST_BE_SEPARATE')
    output.relative_to(project)
    output.mkdir(parents=True, exist_ok=False)
    snapshot = InputSnapshot(project)
    def save(name, data):
        path=output/name;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    def event(phase, **extra):
        with (output/'events.jsonl').open('a') as stream:
            stream.write(json.dumps({'time':datetime.now(timezone.utc).isoformat(),'step':'QI02','phase':phase,'model_calls':0,**extra})+'\n')
    event('START')
    try:
        experiment=source/'03-experiment/qwen-8b';frozen=snapshot.capture(experiment/'dataset.json')
        groups=group_frozen(frozen)
        if len(frozen)!=expected_variants or len(groups)!=expected_originals:
            raise ValueError('DENOMINATOR_MISMATCH')
        approvals_path=source/'02-generation/approved-inputs.json';approvals=snapshot.capture(approvals_path)
        quality_path=quality_root/'quality_scope.json';quality=snapshot.capture(quality_path)
        generations={r['id']:r['references']['generation'] for r in quality['records']}
        # Preserve every observed request's settings; do not infer revision from a model alias.
        templates={}; common=None
        for n,item in enumerate(frozen,1):
            path=experiment/'01-repeat'/f'{n:04d}'/'request.json';request=snapshot.capture(path)
            current=settings(request)
            if common is None: common=current
            if current!=common:raise ValueError('MIXED_REQUEST_CONDITIONS')
            if request['messages'][1]['content']!='Question:\n'+item['question']+'\n\nContext:\n'+item['context']:
                raise ValueError('REQUEST_FROZEN_IDENTITY_MISMATCH')
            templates.setdefault(item['id'].split('/')[0],(request,snapshot.ref(path)))
        snapshot.capture(project/'src/finarch/experiments/01-evaluation/03-execution/qwen_repeated.py',parse=False)
        records=[];public=[]
        frozen_by_id={r['id']:r for r in frozen}
        for parent,variants in groups.items():
            refs={'approved_inputs':snapshot.ref(approvals_path),'frozen_dataset':snapshot.ref(experiment/'dataset.json'),
                  'quality_scope':snapshot.ref(quality_path),'request_template':templates[parent][1]}
            original=None;round_name=None;data={};errors=[]
            try:
                approval=approvals[parent];base,round_name=approved_directory(source,parent,approval)
                for key in ('source','working_input','audit','program','comparison','graph'):
                    ref=approval['files'][key];path=(base/ref['path']).resolve()
                    if not path.is_relative_to(base/round_name):raise ValueError('WRONG_APPROVED_ROUND_OR_PATH')
                    value=snapshot.capture(path)
                    actual=snapshot.ref(path)
                    if not actual or actual['sha256']!=ref['sha256']:raise ValueError('APPROVED_HASH_MISMATCH:'+key)
                    refs[key]=actual
                    if key=='working_input':data=value
                original=public_original(data,parent)
                for identifier in variants:
                    genref=generations[identifier];path=project/genref['path'];gen=snapshot.capture(path)
                    if snapshot.ref(path)!=genref:raise ValueError('GENERATION_HASH_MISMATCH')
                    refs['generation:'+identifier]=genref
                    saved_path=path.with_name('approved-input.json');saved=snapshot.capture(saved_path)
                    if saved!=approval:raise ValueError('VARIANT_APPROVED_PARENT_MISMATCH')
                    refs['approval:'+identifier]=snapshot.ref(saved_path)
                    frozen_item=frozen_by_id[identifier]
                    if gen.get('observation')!={k:frozen_item[k] for k in ('question','context')}:
                        raise ValueError('FROZEN_GENERATION_QC_MISMATCH')
                    request=gen['plan']['request']
                    if any(request[k]!=original[k] for k in ('question','context')):
                        raise ValueError('DERIVATION_ORIGINAL_QC_MISMATCH')
                public.append(original)
                save('public/requests/'+parent+'.json',make_request(original,templates[parent][0]))
            except (KeyError,ValueError,TypeError) as error:
                errors.append(str(error));original=None
            records.append(BaselineRecord(id=parent,status='PREPARED' if original else 'NOT_PREPARED',variants=variants,
                approved_round=round_name,source_dataset=data.get('provenance',{}).get('dataset'),
                reference={k:data.get(k) for k in ('reference_answer','reference_answer_type','reference_precision','answer_metadata')},
                provenance={k:data.get(k) for k in ('raw_id','provenance','context_mapping')},
                qc_sha256=digest({k:original[k] for k in ('question','context')}) if original else None,
                references=refs,skip_reasons=errors))
        counts=Counter(r.source_dataset for r in records if r.status=='PREPARED')
        summary={'originals':len(groups),'variants':len(frozen),'prepared':len(public),'not_prepared':len(groups)-len(public),
                 'FinanceReasoning':counts['FinanceReasoning-native'],'TAT_QA':counts['TAT-QA'],
                 'baseline_calls':0,'semantic_reviewed':0}
        report=BaselineReport(run_id=output.name,source_run=source.name,status='PREPARED_NOT_RUN' if len(public)==len(groups) else 'PARTIAL_NOT_RUN',
            records=records,summary=summary,public_manifest='public/dataset.json',requests_directory='public/requests',request_settings=common,
            limitations=['Original means approved Preparation C/Q, not necessarily raw provider text.',
             'Reference and provenance are private; public JSON allows id/context/question only. Requests contain only fixed system instructions and Q/C.',
             'Original semantic review is NOT_REVIEWED for all records; approval is not proof of semantic validity.',
             'Qwen baseline is deferred. Exact deployed revision is not established by saved model alias; preserve and verify conditions before any future run.',
             'Future Luna-low API quality checks do not substitute for a matched Qwen baseline.'])
        snapshot.verify()
        save('public/dataset.json',public)
        save('private/originals.json',report.model_dump())
        save('sidecar-schema.json',BaselineReport.model_json_schema());save('public-input-schema.json',PublicOriginal.model_json_schema())
        save('summary.json',{'workflow':'original_baseline','status':report.status,**summary,'model_calls':0})
        save('manifest.json',{'snapshot_status':'UNCHANGED','inputs':list(snapshot.references.values()),'missing':sorted(snapshot.missing),
             'outputs':[{'path':p.relative_to(output).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted((output/'public').rglob('*.json'))]})
        (output/'README.md').write_text(Path(__file__).with_name('original-baseline-readme-template.md').read_text().format(run_id=output.name,**summary))
        event('END',status=report.status,**summary)
        return report
    except Exception as error:
        save('failure.json',{'status':'SNAPSHOT_CHANGED' if str(error).startswith('SNAPSHOT_CHANGED') else 'FAIL','reason':str(error)})
        event('FAIL',reason=str(error));raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('source','output','quality-root'):parser.add_argument('--'+key,required=True)
    args=parser.parse_args();print(build(args.source,args.output,args.quality_root).summary)

if __name__=='__main__':main()
