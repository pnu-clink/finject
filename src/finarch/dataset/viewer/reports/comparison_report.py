"""Read recorded production outcomes; never call a model or change its verdict."""
import json
import hashlib
from pathlib import Path
from collections import Counter
resolve_read = __import__('finarch.dataset.90-operations.ordered_artifacts', fromlist=['resolve_read']).resolve_read
audit_root = __import__('finarch.dataset.90-operations.stage_paths', fromlist=['audit_root']).audit_root
generation_root = __import__('finarch.dataset.90-operations.stage_paths', fromlist=['generation_root']).generation_root
candidate_root = __import__('finarch.dataset.90-operations.stage_paths', fromlist=['candidate_root']).candidate_root
LABELS = __import__('finarch.dataset.90-operations.stage_paths', fromlist=['LABELS']).LABELS
save = __import__('finarch.dataset.02-generation.operations.feedback_loop', fromlist=['save']).save

def read(path):
    try:
        return json.loads(path.read_text()) if path.is_file() else None
    except (json.JSONDecodeError, FileNotFoundError):
        # Live writes can be briefly incomplete; never turn them into PASS.
        return None

def outcomes(bundle, round_name):
    directory=bundle/round_name; result={}
    if not directory.exists():return result
    # Carry only already observed outcomes across retries, not future outcomes.
    if round_name!='01-round':
        result=outcomes(bundle,f'{int(round_name[:2])-1:02d}-round')
    summary=read(directory/'summary.json') or {}
    for item in summary.get('results',[]):
        if not item.get('allow_next_stage'):
            result[(item['input_id'],'PIPELINE')]={'status':'EXCLUDED','reason':item.get('reason',''),'stage':item.get('stage','')}
    manifest=read(directory/'graph-next-stage.json') or {}
    for item in manifest.get('blocked',[]):
        case=directory/item['input_id']
        recorded=read(case/'production-plan-failure.json') or read(case/'run.json') or {}
        result[(item['input_id'],'PIPELINE')]={'status':'EXCLUDED','reason':item.get('reason') or recorded.get('reason','Graph or planning failed'),'stage':'03-graph/04-perturbation'}
    for case in sorted(directory.glob('test-*')):
        variants=read(case/'04-perturbation/05-list-candidates/03-result.json')
        if variants is None:continue
        spec=read(case/'04-perturbation/00-receive-input/01-input.json') or {}
        program=read(case/'02-calculation/02-prepare-code/03-program.json') or {}
        facts=program.get('facts',{})
        by_label={v['label']:v for v in variants}
        for label in ['ANSWER']+[v['label'] for v in variants]:
            if label not in LABELS:
                result[(case.name,label)]={'status':'NOT_EVALUATED','reason':'No finalized candidate path for this recorded plan label','stage':'04-perturbation','generation_status':'NOT_EVALUATED','target_signature':None}
                continue
            fail=read(resolve_read(case/generation_root(label)/round_name/'03-result/failure.json'))
            report=read(resolve_read(case/audit_root(label)/round_name/'03-result.json'))
            if report is None:
                pointer=read(resolve_read(case/candidate_root(label)/'latest-audit.json'))
                if pointer:report=read(resolve_read(case/pointer['stage']/'03-result.json'))
            if fail:
                value={'status':'FAIL','reason':fail.get('reason','Generation failed'),'stage':'01-generate-text'}
            elif report:
                value={'status':report.get('status','NOT_EVALUATED'),'reason':report.get('reason',''),'stage':'02-review-and-correct'}
            else:
                value={'status':'NOT_EVALUATED','reason':'No completed audit','stage':'05-text'}
            generation=read(resolve_read(case/generation_root(label)/round_name/'03-result/metadata.json'))
            if generation is None:
                latest=read(resolve_read(case/candidate_root(label)/'latest-realization.json'))
                if latest:generation=read(resolve_read(case/latest['stage']/'03-result/metadata.json'))
            value['generation_status']='NOT_APPLICABLE' if label=='ANSWER' else ('FAIL' if fail else (generation or {}).get('stage16_status','NOT_EVALUATED'))
            target=by_label.get(label,{}).get('plan',{}).get('fact_id') if label.startswith('EA') else spec.get('target')
            fact=facts.get(target,{})
            value['target_signature']={'span':fact.get('span'),'text':fact.get('text')} if fact and label!='ANSWER' else None
            result[(case.name,label)]=value
    return result

def usage_summary(bundle):
    totals=Counter();rounds=Counter();roles=Counter();unknown=0
    for path in bundle.rglob('events.jsonl'):
        for line in path.open():
            try:item=json.loads(line)
            except ValueError:continue
            if item.get('phase')!='USAGE':continue
            n=item.get('cli_invocations')
            if n is None:unknown+=1;continue
            rounds[path.relative_to(bundle).parts[0]]+=n;roles[item.get('role','unknown')]+=n
            usage=item.get('reported_usage') or {}
            for key in ('input_tokens','output_tokens','cached_input_tokens'):
                if isinstance(usage.get(key),(float,int)):totals[key]+=usage[key]
    return {'calls_by_round':dict(rounds),'calls_by_role':dict(roles),'reported_tokens':dict(totals),'unknown_invocations':unknown,'billed_cost':None}

def pipeline_summary(bundle):
    directory=bundle/'01-round'
    summary=read(directory/'summary.json') or {}
    graph=read(directory/'graph-next-stage.json') or {}
    return {'planned':summary.get('planned'), 'processed':summary.get('processed'),
        'calculation_counts':dict(Counter(i.get('status','NOT_EVALUATED') for i in summary.get('results',[]))),
        'generation_eligible':len(graph.get('eligible',[])),
        'calculation_failures':[{'case':i['input_id'],'reason':i.get('reason','')} for i in summary.get('results',[]) if i.get('status')=='FAIL']}

def guidance_application(bundle):
    expected={}
    manifest=read(bundle/'initial-feedback.json') or {}
    source_issues=[]
    if manifest.get('source'):
        source=Path(manifest['source'])
        paths=[]
        for relative,digest in manifest.get('files',{}).items():
            path=source/relative
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
                source_issues.append(str(path))
            else:paths.append(path)
    else:
        paths=list((bundle/'feedback').glob('*/*.json'))
    for path in paths:
        item=read(path)
        if item and item.get('guidance'):
            expected[(item['target_role'],item['axis'])]=hashlib.sha256(item['guidance'].encode()).hexdigest()
    counts=Counter();issues=[];models=Counter();efforts=Counter();fresh=0;total=0
    for path in bundle.glob('01-round/test-*/**/01-request.json'):
        item=read(path)
        if not item or not item.get('prompt_selection'):continue
        total+=1;fresh+=item.get('fresh_session') is True
        models[item.get('model','unknown')]+=1;efforts[item.get('effort','unknown')]+=1
        parts=item['prompt_selection'].get('parts',[]);role=item.get('role')
        axis='ANSWER' if role=='01-preparation.03-calculation.pot' else Path(parts[1]['file']).stem.upper().replace('-','_') if len(parts)>1 else 'UNKNOWN'
        wanted=expected.get((role,axis))
        if wanted:
            applied=any(p.get('sha256')==wanted and hashlib.sha256(p.get('text','').encode()).hexdigest()==wanted for p in parts)
            if applied:counts[role+'/'+axis]+=1
            else:issues.append(str(path.relative_to(bundle)))
    return {'request_count':total,'fresh_session_requests':fresh,'models':dict(models),'efforts':dict(efforts),
        'supplement_applied':dict(counts),'missing_or_mismatched':issues,'initial_source_issues':source_issues,
        'inherited_generated_manifests':len(list(bundle.glob('01-round/test-*/inherited-inputs.json')))}

def audit_condition_check(baseline, comparison):
    def requests(bundle):
        for path in bundle.glob('01-round/test-*/**/01-request.json'):
            item=read(path)
            if not item or item.get('role')!='shared.01-02.02-03.review-and-validation':continue
            definition=item.get('prompt_selection') or {};parts=definition.get('parts',[])
            if len(parts)<2:continue
            axis=Path(parts[1]['file']).stem
            condition={'instruction':definition.get('instruction'),'schema':item.get('response_schema'),
                       'model':item.get('model'),'effort':item.get('effort')}
            digest=hashlib.sha256(json.dumps(condition,sort_keys=True).encode()).hexdigest()
            yield axis,digest,str(path.relative_to(bundle))
    expected={}
    for axis,digest,_ in requests(baseline):expected.setdefault(axis,set()).add(digest)
    matched=0;mismatched=[];unknown=[]
    for axis,digest,path in requests(comparison):
        if axis not in expected:unknown.append(path)
        elif digest in expected[axis]:matched+=1
        else:mismatched.append(path)
    return {'baseline_round':'01-round','compared_fields':['instruction','response_schema','model','effort'],
            'matched':matched,'mismatched':mismatched,'unknown':unknown,
            'all_equal':matched>0 and not mismatched and not unknown}

def build(baseline, comparison, *, baseline_rounds=(1,2,3)):
    baseline=Path(baseline);comparison=Path(comparison)
    columns=[(baseline,f'{n:02d}-round') for n in baseline_rounds]+[(comparison,'01-round')]
    comparison_index=len(columns)-1
    snapshots=[outcomes(*x) for x in columns]
    keys=sorted(set().union(*(set(x) for x in snapshots)))
    rows=[]
    transitions=Counter()
    for key in keys:
        values=[]
        for s in snapshots:
            missing={'status':'NOT_GENERATED','reason':'No matching recorded candidate'}
            if key[1]=='PIPELINE' and any(name==key[0] for name,label in s):
                missing={'status':'NOT_EXCLUDED','reason':'Upstream gates passed; see generated candidate rows'}
            elif (key[0],'PIPELINE') in s:
                missing['reason']='Upstream exclusion: '+s[(key[0],'PIPELINE')].get('reason','')
            values.append(s.get(key,missing))
        transition=values[0]['status']+' → '+values[comparison_index]['status']
        transitions[transition]+=1
        same_target=values[0].get('target_signature')==values[comparison_index].get('target_signature') if values[0].get('target_signature') and values[comparison_index].get('target_signature') else None
        rows.append({'case':key[0],'label':key[1],'results':values,'transition':transition,'same_target':same_target})
    selections=[read(p/'input-selection.json') for p in (baseline,comparison)]
    same_input=all(selections) and selections[0]['sha256']==selections[1]['sha256'] and selections[0]['cases']==selections[1]['cases']
    audit_check=audit_condition_check(baseline,comparison)
    audit_changed=bool(audit_check['mismatched']) if audit_check['matched'] or audit_check['mismatched'] else None
    report={'baseline_run':baseline.name,'comparison_run':comparison.name,'same_input':same_input,
        'input_count':len(selections[0]['cases']) if selections[0] else None,
        'columns':[{'run':p.name,'round':r,'counts':dict(Counter(x['status'] for x in s.values())),
                    'failures_by_type':dict(Counter('IC_SOURCE' if label.startswith('IC_SOURCE') else 'IC_VALUE' if label.startswith('IC_VALUE') else 'IC_RELATION' if label.startswith('IC_RELATION') else 'EA' if label.startswith('EA') else label for (_,label),x in s.items() if x['status']=='FAIL')),
                    'dependency_blocked':sum(x['status']=='FAIL' and x.get('reason','').startswith('IC_VALUE_BEFORE_AUDIT_REQUIRED') for x in s.values()),
                    'generation_counts':dict(Counter(x.get('generation_status','NOT_APPLICABLE') for x in s.values()))}
                   for (p,r),s in zip(columns,snapshots)],
        'transitions':dict(transitions),'rows':rows,'same_target_count':sum(r['same_target'] is True for r in rows),'different_target_count':sum(r['same_target'] is False for r in rows),
        'transitions_by_baseline_round':{f'{round_number:02d}-round':dict(Counter(row['results'][n]['status']+' → '+row['results'][comparison_index]['status'] for row in rows)) for n,round_number in enumerate(baseline_rounds)},
        'same_target_transitions':dict(Counter(r['transition'] for r in rows if r['same_target'] is True)),
        'evaluation_prompt_changed':audit_changed,'audit_condition_check':audit_check,
        'interpretation':'Combined generation and evaluation-guidance change. Do not attribute all outcome changes solely to generation quality.' if audit_changed else 'Audit conditions are checked against the baseline first round. Fresh code can still change eligibility; compare matched candidates separately.',
        'scope':'Same-input development-set comparison; fresh code and text may change candidate targets. Not an unseen-data generalization estimate.',
        'guidance':read(comparison/'initial-feedback.json'),
        'pipeline':{p.name:pipeline_summary(p) for p in (baseline,comparison)},
        'guidance_application':guidance_application(comparison),
        'usage':{p.name:usage_summary(p) for p in (baseline,comparison)}}
    contract=read(comparison/'experiment-contract.json') or {}
    effort_comparison=contract.get('changed_variable')=='dtt.realize reasoning effort: none -> low'
    report['title']='문장 생성 추론 비교 · none → low' if effort_comparison else '추가 지침 적용 전·후 비교'
    report['change_description']=('문장 생성만 Luna none에서 low로 변경했습니다. 보완 지침은 같고 계산·의미 검사는 none입니다.' if effort_comparison else '')
    save(comparison/'comparison-report.json',report)
    save(baseline/'comparison-link.json',{'comparison_run':comparison.name})
    summary='\n'.join('- '+c['run']+' '+c['round']+': '+', '.join(f'{k} {v}' for k,v in c['counts'].items()) for c in report['columns'])
    template=Path(__file__).with_name('comparison-readme.md').read_text()
    evaluation_note=('생성과 검사 지침을 함께 바꿨으므로 생성만의 효과로 해석하지 않습니다.' if audit_changed else '검사 프롬프트·응답 스키마·모델·추론 설정을 이전 실행의 첫 차수 실제 요청과 대조했습니다. 검사 동일 여부와 불일치 목록은 comparison-report.json에 있습니다.')
    (comparison/'README.md').write_text(template.format(**report,summary=summary,evaluation_note=evaluation_note))
    RunLogs = __import__('finarch.shared.run_logging.run_logs', fromlist=['RunLogs']).RunLogs
    logs=RunLogs.for_case(comparison)
    logs.write('pipeline.log','comparison.build_report',stage='comparison-report',phase='END')
    logs.write('detail.log','comparison.build_report',stage='comparison-report',value={'artifact':str(comparison/'comparison-report.json'),'columns':report['columns'],'same_input':same_input})
    return report

if __name__=='__main__':
    import sys
    r=build(*sys.argv[1:3]);print(json.dumps({k:v for k,v in r.items() if k not in ('rows','guidance')},indent=2))
