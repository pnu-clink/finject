"""Portable evaluation snapshot: displayed evidence, no production call history."""
import base64
import gzip
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

SELECTION_POLICY = 'ALL_SEVEN_AUTOMATIC_PASS_NO_HUMAN_REJECTION'
REQUIRED_VARIANTS = ('01-ic-value-before', '02-ic-value-after', '03-ic-source-type-1',
                     '04-ic-source-type-2', '05-ic-relation', '06-ea-earlier-input',
                     '07-ea-later-input')


def eligible_record(folder, phase, state):
    """Require automatic PASS; human Accept is optional, explicit Reject is not."""
    from importlib import import_module
    policy = import_module('finarch.dataset.03-release.export_policy')
    if not isinstance(state, dict) or state.get('status') != 'PASS':
        return False
    recorded, _ = policy.review(folder, phase)
    return policy.current_decision(state, recorded) not in policy.REJECTED


def eligible_case(bundle, case, detail):
    """Export the complete seven-type group or none; never require human Accept."""
    if not eligible_record(Path(detail['path']), 'preparation', detail.get('artifacts',{}).get('run.json',{})):
        return False
    origins=detail.get('generation_origins',{})
    if any(variant not in origins for variant in REQUIRED_VARIANTS):
        return False
    return all(eligible_record(bundle/'02-generation'/origins[variant]/case/variant,
                               'generation',detail.get('generation',{}).get(variant+'/run.json',{}))
               for variant in REQUIRED_VARIANTS)


def keep_artifact(relative):
    path=Path(relative)
    if re.fullmatch(r'03-calculation/[^/]+/03-LLM-review-evidence/01-request/03-result.json',relative):return True
    if any(part in {'stage-history','repair-history','interrupted-attempts','08-records','01-request','logs'} for part in path.parts):return False
    if path.suffix not in {'.json','.py'}:return False
    if any(word in relative.lower() for word in ('raw-response','request','transport','feedback-ref','schema-check','token','usage','history','trace-events')):return False
    if len(path.parts)==1:return path.name in {'run.json','data.json','reference-data.json','data-comparison.json'}
    stage=path.parts[0]
    if stage=='01-source':return True
    if stage in {'02-review','02-review-and-correct','02-audit-meaning'}:
        return path.name in {'accepted-input.json','accepted-audit.json'} or '03-record-result' in path.parts or path.name=='03-result.json'
    if stage=='03-calculation':
        return path.suffix=='.py' or any(s in relative for s in ('program.json','comparison.json','transformation.json','stage-output.json','02-prepare-code/','03-preserve-response-and-code/','05-execute-and-compare/','00-condition-recheck/','01-LLM-generate-code/03-result.json','02-LLM-generate-code/03-result.json','source-diagnosis.json','grounding-review.json','04-execute-python/','03-execute-python/','05-record-calculation-artifacts/','04-compare-answer/','04-apply-correction/'))
    if stage=='04-graph':return '01-read-calculation' not in path.parts
    if stage=='05-verification':return 'LLM' not in relative and '01-collect-artifacts' not in relative
    if stage in {'06-exception-handler','04-exception-handler'}:
        return path.name in {'exception.json','feedback.json','01-result.json','03-result.json','failure.json'}
    if stage in {'07-human-review','05-human-review','04-human-review'}:
        return path.name in {'01-result.json','review-note.json'}
    if stage=='01-perturbation':return path.name in {'03-result.json','02-graph.json','01-inherited-plan.json'}
    if stage=='02-generate-text':return path.name in {'01-input.json','03-edit-check.json','04-observation.json','05-patches.json','02-place-paired-sentence.json','failure.json'}
    if stage=='03-validation':return len(path.parts)==2 and path.name in {'03-result.json','04-comparison.json','failure.json'}
    return False


def inline_json(value):
    return json.dumps(value,ensure_ascii=False,separators=(',',':')).replace('&','\\u0026').replace('<','\\u003c').replace('>','\\u003e').replace('\u2028','\\u2028').replace('\u2029','\\u2029')


def build(root, specifications, initial_view=None):
    from finarch.dataset.viewer.server import batch_data, batch_path
    from finarch.dataset.viewer.assets import render
    if not isinstance(specifications,list) or not 1<=len(specifications)<=10:raise ValueError('내보낼 실행을 선택해 주세요.')
    batches=[];blobs=[];seen=set();signature=hashlib.sha256()
    for spec in specifications:
        if not isinstance(spec,dict):raise ValueError('실행 선택 형식이 올바르지 않습니다.')
        name=spec.get('name');bundle=batch_path(root,name)
        if name in seen:raise ValueError('실행이 중복되었습니다.')
        seen.add(name)
        if not (bundle/'01-preparation').is_dir():raise ValueError('Preparation/Generation 실행만 내보낼 수 있습니다.')
        requested=spec.get('cases')
        if requested is not None and (not isinstance(requested,list) or not requested or any(not isinstance(x,str) or not re.fullmatch(r'test-\d+',x) for x in requested)):raise ValueError('문항 선택이 올바르지 않습니다.')
        overview=batch_data(root,name,spec.get('round'),requested[0] if requested else None,artifact_filter=keep_artifact)
        selected=set(requested) if requested is not None else None
        candidates=[r for r in overview['runs'] if selected is None or Path(r.get('case_path',r['path'])).name in selected]
        if selected is not None and len(candidates)!=len(selected):raise ValueError('선택한 문항 중 실행에 없는 번호가 있습니다.')
        batch={k:v for k,v in overview['batch'].items() if k in {'name','layout','round','rounds','preparation_rounds','generation_rounds','completion_report','generation_overview','preparation_queue','generation_queue','review_gate'}}
        # Preserve displayed aggregates, not the report's per-case attachment rows.
        if batch.get('completion_report'):
            report=batch['completion_report']
            batch['completion_report']={'status':report.get('status'),**{phase:{key:value for key,value in report.get(phase,{}).items() if key in {'rounds','runtime'}} for phase in ('preparation','generation')}}
        if batch.get('review_gate'):batch['review_gate']={'allow_generation':batch['review_gate'].get('allow_generation')}
        if batch.get('preparation_queue'):batch['preparation_queue']={key:value for key,value in batch['preparation_queue'].items() if key in {'limit','completed','planned'}}
        if batch.get('generation_queue'):batch['generation_queue']={key:(len(value) if isinstance(value,(list,dict)) else value) for key,value in batch['generation_queue'].items() if key in {'limit','active','pending','generation','source'}}
        # The exported snapshot includes one selected round, with carried evidence.
        batch['rounds']=[batch['round']];batch['generation_overview']=[x for x in batch.get('generation_overview',[]) if selected is None or x['case'] in selected]
        for item in batch['generation_overview']:item.pop('review',None)
        summaries=[];case_entries=[]
        for candidate in candidates:
            case=Path(candidate.get('case_path',candidate['path'])).name
            if not eligible_record(Path(candidate['path']), 'preparation', candidate.get('artifacts',{}).get('run.json',{})):
                continue
            detail=candidate if not candidate.get('summary_only') else batch_data(root,name,batch['round'],case,detail_only=True,artifact_filter=keep_artifact)['runs'][0]
            if not eligible_case(bundle,case,detail):
                continue
            variants=list(REQUIRED_VARIANTS)
            allowed=set(variants)
            for key in ('generation','generation_snapshots','generation_origins'):
                detail[key]={k:v for k,v in detail.get(key,{}).items() if k.split('/')[0] in allowed}
            summary=detail.pop('list_entry',None) or candidate
            summary['decisions']={}
            if not detail.get('summary_only'):
                detail['decisions']={}
                for key in list(summary.get('artifacts',{})):
                    if key.endswith('/decision.json'):summary['artifacts'].pop(key)
            # Relative display paths make the package independent of the author's disk.
            prefix=str(bundle.parent.resolve())+'/'
            raw=json.dumps(detail,ensure_ascii=False,separators=(',',':')).replace(prefix,'reports/run/')
            digest=hashlib.sha256(raw.encode()).hexdigest();signature.update((name+case+digest).encode())
            ident='evaluation-case-'+str(len(blobs))
            blobs.append((ident,base64.b64encode(gzip.compress(raw.encode(),mtime=0)).decode()))
            summaries.append(json.loads(json.dumps(summary,ensure_ascii=False).replace(prefix,'reports/run/')))
            case_entries.append({'case':case,'blob':ident,'sha256':digest,'variants':sorted(variants)})
        if not case_entries:
            raise ValueError('7유형 모두 자동 검증 PASS이며 어느 유형에도 Reject가 없는 문항이 없습니다.')
        eligible={entry['case']:set(entry['variants']) for entry in case_entries}
        batch['generation_overview']=[item for item in batch['generation_overview']
                                      if item['case'] in eligible and item['path'].split('/')[0] in eligible[item['case']]]
        batches.append({'batch':batch,'runs':summaries,'cases':case_entries})
    package={'format':'finarch-evaluation-html-v1','id':signature.hexdigest(),'selection_policy':SELECTION_POLICY,'created_at':datetime.now(timezone.utc).isoformat(),'batches':batches,'initial_view':initial_view or {}}
    first=batches[0]
    payload={'format':'fin-arch-viewer-v1','live':False,'evaluation':package,'batch':first['batch'],'runs':first['runs']}
    html=render().replace('__FINARCH_DATA__',inline_json(payload)).replace('<head>','<head><script>window.FINARCH_EVALUATION=true;</script>',1)
    encoded=''.join(f'<script type="application/octet-stream" id="{ident}">{value}</script>' for ident,value in blobs)
    html=html.replace('<script id="data"',encoded+'<script id="data"',1)
    return html.encode('utf-8'),{'runs':[x['batch']['name'] for x in batches],'cases':sum(len(x['cases']) for x in batches),'bytes':len(html.encode('utf-8'))}
