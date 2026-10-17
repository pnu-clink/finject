candidate_root = __import__('finarch.dataset.90-operations.stage_paths', fromlist=['candidate_root']).candidate_root
LABELS = __import__('finarch.dataset.90-operations.stage_paths', fromlist=['LABELS']).LABELS
ordered_path = __import__('finarch.dataset.90-operations.ordered_artifacts', fromlist=['ordered_path']).ordered_path
"""HR01: production evidence + current Stage17 audit, without Stage18 gating."""
import hashlib
import json
from pathlib import Path
RunContext = __import__('finarch.dataset.90-operations.staging', fromlist=['RunContext']).RunContext
read = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['read']).read
digest = __import__('finarch.dataset.02-generation.02-generate-text.dtt_realize', fromlist=['digest']).digest
from finarch.dataset.shared.review.dtt_audit import prepare, evaluate_saved


def candidate_current(root, review):
    """Logs and post-freeze model responses cannot invalidate production review."""
    try:
        if not all(digest(root/p)==h for p,h in review['reference_hashes'].items()):return False
        if review['variant']!='ANSWER':
            variant=next(v for v in read(root/'04-perturbation/05-list-candidates/03-result.json') if v['label']==review['variant'])
            if hashlib.sha256(json.dumps(variant['plan'],sort_keys=True).encode()).hexdigest()!=review['plan_sha256']:return False
        return True
    except (OSError,ValueError,KeyError,StopIteration):return False


def build(case_dir, revision='production-v1'):
    case=Path(case_dir).resolve();ctx=RunContext.resume(case,{},case.name)
    family='06-human-review/01-collect-results/'+revision
    if (case/family).exists():raise ValueError('HUMAN_REVIEW_BUNDLE_ALREADY_EXISTS')
    variants=read(case/'04-perturbation/05-list-candidates/03-result.json');reviews=[]
    with ctx.trace.activate(),ctx.trace.span('human_review.prepare',stage='06-human-review',step='01-collect-results',role='python'):
        for label in ['ANSWER']+[v['label'] for v in variants]:
            refs=['00-data-preparation/01-select-input/01-input.json','02-calculation/02-prepare-code/03-program.json','03-graph/04-save-graph/01-graph.json']
            item={'variant':label,'status':'NOT_EVALUATED','human_decision':'PENDING','stage18':'EXCLUDED_FROM_PRODUCTION',
                  'recovery_review':'DEFERRED_BY_USER','plan_sha256':None}
            try:
                request,binding=prepare(case,label);item.update(binding)
                pointer=candidate_root(label)+'/latest-audit.json';refs.append(pointer)
                path=read(case/pointer)['stage'];audit=read(case/path/'03-result.json');saved=read(case/path/'01-input/check.json')
                for k in ('observation_sha256','plan_sha256','stage16_ref'):
                    if saved.get(k)!=binding.get(k):raise ValueError('AUDIT_BINDING_STALE')
                raw=read(case/path/'audit/02-raw-response.json')
                if isinstance(raw,dict) and set(raw)=={'text'}:raw=json.loads(raw['text'])
                checked=evaluate_saved(request,raw,audit)
                if checked['status']!=audit['status'] or checked['findings']!=audit['findings']:raise ValueError('AUDIT_REPORT_CHANGED')
                refs.extend([path+'/03-result.json',path+'/01-input/check.json',path+'/audit/02-raw-response.json'])
                if binding['stage16_ref']:
                    refs.extend(binding['stage16_ref']+'/'+n for n in ('04-final-observation.json','01-input.json','03-result/patches.json','03-result/metadata.json','03-result/validation.json'))
                    pp=candidate_root(label)+'/latest-realization.json'
                    if (case/pp).exists():refs.append(pp)
                item.update(status='AWAITING_HUMAN' if audit['status']=='PASS' else audit['status'],
                            reason='Scoped semantic audit completed; human decision pending' if audit['status']=='PASS' else audit.get('reason') or audit.get('state_reason',''),
                            final_observation={k:request[k] for k in ('context','question')},intent=request['intent'],
                            semantic_audit=audit,audit_ref=path,answer_role='conditional Python results, not an independent model answer')
            except (OSError,ValueError,KeyError,TypeError) as error:
                item.update(reason=str(error).splitlines()[0],status='NOT_EVALUATED')
            refs=[ordered_path(p) for p in refs]
            item['reference_hashes']={p:digest(case/p) for p in refs if (case/p).is_file()}
            item['review_sha256']=hashlib.sha256(json.dumps(item,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            ctx.save(family+'/'+LABELS[label]+'.json',item);reviews.append(item)
        ctx.save(family+'/08-review-index.json',reviews)
        index=case/'06-human-review/03-result.json'
        if index.exists():ctx.save(family+'/previous-review-index.json',read(index))
        tmp=index.with_suffix('.tmp');tmp.write_text(json.dumps(reviews,ensure_ascii=False,indent=2)+'\n');tmp.replace(index);ctx.trace.artifact('06-human-review/03-result.json')
        ctx.save_text(family+'/README.md',f'''♪ People are ready to review ♪ {case.name}

The order of reading: Python graphs → Type change plans → 16The final text 17The status is before the person judges. Automatic audit passing is different from the person approved. 18And the first time I put the preliminary answer to the judgment base, 6 The person\x27s judgment directly records the reviewer, EU authorization/correction request/external. The reviewed list is not invalidated by log addition connected to the production output.1This is the set of records created by this README created by this common template.
''')
    return {'case':case.name,'ready':sum(r['status']=='AWAITING_HUMAN' for r in reviews),'total':len(reviews)}
