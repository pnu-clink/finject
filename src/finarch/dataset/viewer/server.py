"""One local viewer reads the batches in reports/run; never generates per-run HTML."""
import argparse
import hashlib
import json
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
import webbrowser

from finarch.dataset.viewer.build import collect, TEMPLATE
from finarch.dataset.viewer.summary_reader import read_generation_summary
from finarch.dataset.viewer.response_encoding import encode
import gzip
from finarch.dataset.viewer.comparison import enrich
from finarch.dataset.schemas.registry import CONTRACTS, describe, resolve_schema_id
describe_prompt = __import__('finarch.dataset.02-generation.02-generate-text.realization_prompts', fromlist=['describe_prompt']).describe_prompt
from finarch.dataset.shared.review.audit_prompts import describe_prompt as describe_audit_prompt

PROJECT = (Path(__file__).resolve().parent / '../../../..').resolve()
RUNS = PROJECT / 'reports' / 'run'


@lru_cache(maxsize=4)
def _result_external_index(path, file_stamp, manifest_stamp):
    """Read the verified consolidated labels once per changed snapshot."""
    result = Path(path)
    raw = result.read_bytes()
    manifest = json.loads((result.parent / 'manifest.json').read_text())
    if hashlib.sha256(raw).hexdigest() != manifest['files']['00-input.json']['sha256']:
        return {}
    rows = json.loads(raw)
    return {row['id']: row['external_knowledge'] for row in rows if
            isinstance(row.get('external_knowledge'), dict)}


def result_external_index(bundle):
    result = bundle / 'results/00-input.json'
    manifest = result.parent / 'manifest.json'
    if not result.is_file() or not manifest.is_file() or result.is_symlink() or manifest.is_symlink():
        return {}
    try:
        return _result_external_index(str(result), result.stat().st_mtime_ns, manifest.stat().st_mtime_ns)
    except (OSError, ValueError, KeyError):
        return {}


def generation_view(generation, rounds, selected, case_name, *, artifact_filter=None, final_only=False):
    """Keep prior variant outputs visible without presenting them as new calls."""
    artifacts={};snapshots={};origins={};latest={}
    for round_name in rounds:
        if not selected or round_name>selected:continue
        parent=generation/round_name/case_name
        if not parent.is_dir() or parent.is_symlink():continue
        for variant in sorted(parent.iterdir()):
            if not variant.is_dir() or variant.is_symlink():continue
            if final_only:
                latest[variant.name]=(round_name,variant)
                continue
            content=collect(variant,allow_partial=True,artifact_filter=artifact_filter)
            prefix=variant.name+'/'
            artifacts={key:value for key,value in artifacts.items() if not key.startswith(prefix)}
            artifacts.update({prefix+key:value for key,value in content['artifacts'].items()})
            snapshots[variant.name]=content['snapshot_sha256'];origins[variant.name]=round_name
    if final_only:
        # Never fall back to an earlier PASS when the last saved variant failed.
        for name,(round_name,variant) in sorted(latest.items()):
            if (read_optional(variant/'run.json') or {}).get('status')!='PASS':continue
            content=collect(variant,allow_partial=True,artifact_filter=artifact_filter)
            artifacts.update({name+'/'+key:value for key,value in content['artifacts'].items()})
            snapshots[name]=content['snapshot_sha256'];origins[name]=round_name
    return {'generation':artifacts,'generation_snapshots':snapshots,'generation_origins':origins}


def read_optional(path):
    if not path.is_file() or path.is_symlink(): return None
    try:
        return json.loads(path.read_text()) if path.suffix == '.json' else path.read_text()
    except (OSError, ValueError) as error:
        return {'read_error':str(error)}


def batch_path(root, name):
    if not name or name in ('.','..') or '/' in name or '\\' in name:
        raise ValueError('INVALID_RUN_NAME')
    target = root / name
    if target.is_symlink() or not target.is_dir() or target.resolve().parent != root.resolve():
        raise ValueError('UNKNOWN_RUN')
    return target


def list_batches(root):
    # [VW01] docs/02-architecture.md#VW01 The resulting folder does not copy or write.
    if not root.exists(): return []
    result=[]
    for item in root.iterdir():
        if not item.is_dir() or item.is_symlink(): continue
        # Dataset selection contains datasets, never documentation or analysis reports.
        report_markers = ('documentation.json', 'failure-review.json', 'json-context-adapter-check.json',
                          'graph-syntax-samples.json', 'finance-preflight.json', 'quality-api-check.json',
                          'coefficient-policy.json', 'pair_manifest.json', 'response_screen.json',
                          'quality_scope.json')
        if any((item / marker).is_file() for marker in report_markers):
            continue
        if not ((item / '01-preparation').is_dir() or (item / 'results/00-input.json').is_file()
                or (item / 'run.json').is_file() or any(item.glob('0[123]-round'))
                or any(item.glob('*/events.jsonl')) or any(item.glob('*/run.json'))):
            continue
        # Independent source-review reports have their own selector and no Preparation rounds.
        if (read_optional(item/'config.json') or {}).get('workflow') in ('knowledge_review','phi_two'): continue
        # Run-level progress already tracks updates; do not walk every request
        # artifact on each three-second browser poll for a hundred-case run.
        patterns=('summary.json','run.json','events.jsonl','loop-summary.json',
                  '0*-round/summary.json','0*-round/production-progress.json',
                  'test-*/run.json','0*-round/test-*/run.json','01-preparation/summary.json','01-preparation/test-*/run.json')
        dates=[p.stat().st_mtime for pattern in patterns for p in item.glob(pattern) if not p.is_symlink()]
        result.append({'name':item.name, 'display_name':(read_optional(item/'run-info.json') or {}).get('display_name',item.name), 'summary':read_optional(item/'summary.json'),
                       'evaluation_exportable':(item/'01-preparation').is_dir(),
                       'modified':max(dates,default=item.stat().st_mtime)})
    return sorted(result,key=lambda item:item['name'],reverse=True)


def round_failure_counts(bundle):
    counts=[]
    for number in range(1,4):
        directory=bundle/f'{number:02d}-round'
        if not directory.is_dir():
            counts.append({'round':number,'count':None,'status':'NOT_STARTED'});continue
        keys=set();verdict=read_optional(directory/'05-text/03-final-validator/03-result.json') or {}
        progress=read_optional(directory/'production-progress.json') or {}
        summary=read_optional(directory/'summary.json') or {}
        for row in summary.get('results',[]):
            if row.get('status')=='FAIL':keys.add((row.get('input_id'),'ANSWER'))
        for name,row in progress.get('cases',{}).items():
            if row.get('status')=='ERROR':keys.add((name,'PIPELINE'))
            for phase in ('generation','audit'):
                for result in row.get(phase,{}).get('results',[]):
                    if result.get('status')=='FAIL':keys.add((name,result['label']))
        resolve_read = __import__('finarch.dataset.90-operations.ordered_artifacts', fromlist=['resolve_read']).resolve_read
        audit_root = __import__('finarch.dataset.90-operations.stage_paths', fromlist=['audit_root']).audit_root
        generation_root = __import__('finarch.dataset.90-operations.stage_paths', fromlist=['generation_root']).generation_root
        for case in directory.glob('test-*'):
            variants=read_optional(case/'04-perturbation/05-list-candidates/03-result.json') or []
            for label in ['ANSWER']+[v['label'] for v in variants]:
                audit=read_optional(resolve_read(case/audit_root(label)/directory.name/'03-result.json')) or {}
                failure=read_optional(resolve_read(case/generation_root(label)/directory.name/'03-result/failure.json')) or {}
                if audit.get('status')=='FAIL' or failure.get('status')=='FAIL':keys.add((case.name,label))
        for item in verdict.get('failures',[]):keys.add((item['case'],item['label']))
        counts.append({'round':number,'count':len(keys),'status':'FINISHED' if verdict else 'RUNNING'})
    return counts


def result_report(bundle):
    """Compare completed validator snapshots; absence in an unfinished round is not success."""
    rounds=[]
    keys=set()
    for number in range(1,4):
        directory=bundle/f'{number:02d}-round'
        verdict=read_optional(directory/'05-text/03-final-validator/03-result.json')
        errors={(x['case'],x['label']):x for x in (verdict or {}).get('failures',[])}
        keys.update(errors)
        guidance=[]
        for path in sorted((directory/'05-text/04-LLM-build-feedback').glob('*/*/03-result.json')):
            value=read_optional(path) or {}
            if value.get('guidance'):
                guidance.append({k:value.get(k) for k in ('axis','version','changes','guidance')})
        rounds.append({'round':number,'complete':bool(verdict),'started':directory.exists(),
                       'errors':errors,'guidance':guidance,'verdict':verdict})
    rows=[]
    for case,label in sorted(keys):
        cells=[];failed_before=False
        for item in rounds:
            error=item['errors'].get((case,label))
            if error:
                state='FAIL';failed_before=True
            elif not item['complete']:
                state='PENDING' if item['started'] else 'NOT_RUN'
            else:
                state='RESOLVED' if failed_before else 'NO_FAILURE'
            cells.append({'status':state,'reason':error.get('reason','') if error else ''})
        rows.append({'case':case,'label':label,'rounds':cells})
    overview=[]
    previous=set()
    for item in rounds:
        current=set(item['errors'])
        overview.append({'round':item['round'],'complete':item['complete'],
                         'failed':len(current) if item['complete'] else None,
                         'resolved':len(previous-current) if item['complete'] and item['round']>1 else None,
                         'guidance':item['guidance']})
        if item['complete']:previous=current
    first=rounds[0]['verdict'] or {}
    return {'rounds':overview,'rows':rows,'exclusions':first.get('upstream_exclusions',[]),
            'status':(read_optional(bundle/'loop-summary.json') or {}).get('status','RUNNING')}


def compact_case(case, states):
    artifacts={}
    for relative in ('run.json','00-data-preparation/01-select-input/01-input.json','04-perturbation/05-list-candidates/03-result.json','06-human-review/03-result.json'):
        value=read_optional(case/relative)
        if value is not None:artifacts[relative]=value
    artifacts.setdefault('run.json',{'status':'INCOMPLETE'})
    artifacts['run.json']={k:v for k,v in artifacts['run.json'].items() if k not in ('events','log_summary')}
    variants=artifacts.get('04-perturbation/05-list-candidates/03-result.json',[])
    artifacts['04-perturbation/05-list-candidates/03-result.json']=[{k:v for k,v in item.items() if k!='plan'} for item in variants]
    statuses={label:value for (name,label),value in states.items() if name==case.name}
    return {'path':str(case),'artifacts':artifacts,'summary_only':True,'status_by_label':statuses,'decisions':{},'stage_flow':{},'artifact_aliases':{},'snapshot_sha256':''}


def preparation_list_metadata(case):
    """Read recorded sources regardless of outcome, and the first passing round."""
    record = read_optional(case / 'run.json') or {}
    result = {'sources': [], 'pass_round': None, 'active_round': record.get('active_round'), 'record_path': str(case / 'run.json')}
    passed = [r for r in record.get('rounds', []) if r.get('status') == 'PASS']
    round_name = (passed[0].get('round') if passed else record.get('active_round'))
    active = case / (record.get('active_round') or '')
    if record.get('status') == 'PASS' and round_name:
        result['pass_round'] = int(round_name.split('-')[0])
    for relative in ('03-calculation/05-record-calculation-artifacts/03-program.json',
                     '03-calculation/02-prepare-code/03-program.json'):
        program = read_optional(active / relative)
        if not isinstance(program, dict):
            continue
        allowed = ('IN_CONTEXT_DATA', 'EXTERNAL_RULE', 'EXTERNAL_DATA')
        declared = set(program.get('calculation_input_sources') or [])
        declared.update(u.get('kind') for u in program.get('source_usage', []) if isinstance(u, dict))
        result['sources'] = [s for s in allowed if s in declared]
        result['source_path'] = str(active / relative)
        break
    return result


def compact_preparation_case(case, requested_round=None):
    """Keep list identity, answer corrections and decisions without call payloads."""
    from finarch.dataset.viewer.preparation_paths import select_round
    case_root=case
    list_metadata=preparation_list_metadata(case_root)
    case, actual_round=select_round(case,requested_round,read_optional(case/'run.json'))
    if case is None:
        return {'path':str(case_root),'artifacts':{'run.json':{'status':'NOT_RUN'}},'summary_only':True,'layout':'preparation-generation-v1','round':None,'preparation_list':list_metadata}
    artifacts={}
    for relative in ('run.json','data.json','01-source/01-receive-input/01-input.json',
                     '03-calculation/05-record-calculation-artifacts/02-comparison.json',
                     '03-calculation/04-compare-answer/01-comparison.json',
                     '07-human-review/03-record-decision/decision.json',
                     '07-human-review/02-record-decision/decision.json',
                     '05-human-review/02-record-decision/decision.json'):
        value=read_optional(case/relative)
        if value is not None:artifacts[relative]=value
    from finarch.dataset.viewer.preparation_paths import add_read_aliases
    add_read_aliases(artifacts,{})
    report=artifacts.get('run.json',{'status':'INCOMPLETE'})
    artifacts['run.json']={k:v for k,v in report.items() if k not in ('events','log_summary','audit')}
    artifacts['00-data-preparation/01-select-input/01-input.json']=artifacts.get('data.json') or artifacts.get('01-source/01-receive-input/01-input.json',{})
    # One small search/identity record; source tables and span maps belong to detail.
    sample=artifacts['00-data-preparation/01-select-input/01-input.json']
    sample={k:sample[k] for k in ('id','raw_id','question','context','provenance') if k in sample}
    sample.setdefault('id',case_root.name)
    sample['provenance']={k:v for k,v in (sample.get('provenance') or {}).items() if k in ('name','dataset','source_id')}
    artifacts['00-data-preparation/01-select-input/01-input.json']=sample
    for relative in ('data.json','01-source/01-receive-input/01-input.json'):
        if relative in artifacts:artifacts[relative]={k:v for k,v in artifacts[relative].items() if k=='reference_answer'}
    for stage in ('07-human-review','06-exception-handler','05-verification','04-graph','03-calculation','02-review','02-review-and-correct','01-source'):
        if (case/stage).is_dir():
            artifacts[stage+'/__summary-only.json']={};break
    return {'path':str(case),'artifacts':artifacts,'layout':'preparation-generation-v1','preparation_list':list_metadata,
            'round':actual_round,'case_path':str(case_root),'carried_round':bool(actual_round and actual_round!=requested_round),'summary_only':True,'status_by_label':{'ANSWER':artifacts['run.json']},
            'decisions':{},'stage_flow':{},'artifact_aliases':{},'snapshot_sha256':''}


def generation_overview(generation, rounds, selected):
    """Read compact round statuses and current human decisions for all cases."""
    latest={}
    for number in rounds:
        if selected and number>selected:continue
        progress=read_optional(generation/number/'progress.json') or {}
        for case,items in progress.get('cases',{}).items():
            for label,item in items.items():
                latest[(case,label)]=item
    result=[]
    for (case,label),item in latest.items():
        folder=generation.parent/item['path']
        result.append({'case':case,'path':folder.name+'/run.json','record':{'status':item['status']},
                       'review':read_optional(folder/'05-human-review/02-record-decision/decision.json') or read_optional(folder/'05-human-review/decision.json') or read_optional(folder/'04-human-review/02-record-decision/decision.json'),
                       'waiting':{'status':(read_optional(folder/'05-human-review/01-result.json') or {}).get('status')}})
    return result


def viewer_review_gate(bundle):
    """Reuse a saved gate only while every recorded input and case marker is unchanged."""
    evaluate = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['evaluate']).evaluate
    path=bundle/'01-preparation/review-gate.json'
    saved=read_optional(path)
    if isinstance(saved,dict) and saved.get('allow_generation') and saved.get('approved_inputs'):
        try:
            stamp=path.stat().st_mtime_ns
            selection=bundle/'input-selection.json'
            names=(read_optional(selection) or {})['cases']
            paths=[selection]+[bundle/'01-preparation'/name/'run.json' for name in names]
            for name,entry in saved['approved_inputs'].items():
                for record in entry['files'].values():
                    paths.append(bundle/'01-preparation'/name/record['path'])
            # The active verification verdict participates in snapshot() as well.
            for name in saved['approved']:
                marker=read_optional(bundle/'01-preparation'/name/'run.json') or {}
                if marker.get('active_round'):
                    paths.append(bundle/'01-preparation'/name/marker['active_round']/'05-verification/08-record-verdict/01-result.json')
            if all(not p.is_symlink() and max(p.stat().st_mtime_ns,p.stat().st_ctime_ns)<=stamp for p in paths):
                return saved
        except (KeyError,OSError,TypeError):
            pass
    return evaluate(bundle,persist=False)


def batch_data(root, name, round_name=None, case_name=None, *, detail_only=False, artifact_filter=None, final_only=False):
    # [VW02] docs/02-architecture.md#VW02 Read the case, log, and text code of the selected execution and send it to the screen data.
    bundle=batch_path(root,name)
    if (bundle/'json-context-adapter-check.json').is_file():
        from finarch.dataset.viewer.reports.json_context_adapter import view
        return view(bundle)
    if (bundle/'documentation.json').is_file():
        from finarch.dataset.viewer.reports.documentation import view
        return view(bundle)
    if (bundle/'failure-review.json').is_file():
        from finarch.dataset.viewer.reports.failure_review import view
        return view(bundle)
    if (bundle/'graph-syntax-samples.json').is_file():
        from finarch.dataset.viewer.reports.graph_syntax_samples import view
        return view(bundle)
    if (bundle/'finance-preflight.json').is_file():
        from finarch.dataset.viewer.reports.finance_preflight import view
        return view(bundle)
    if (bundle/'quality-api-check.json').is_file():
        from finarch.dataset.viewer.reports.quality_api_check import view
        return view(bundle)
    if (bundle/'coefficient-policy.json').is_file():
        from finarch.dataset.viewer.reports.coefficient_policy import view
        return view(bundle)
    if (bundle/'pair_manifest.json').is_file():
        from finarch.dataset.viewer.reports.source_pair_review import view
        return view(bundle)
    if (bundle/'private/originals.json').is_file():
        from finarch.dataset.viewer.reports.original_baseline import view
        return view(bundle)
    if (bundle/'response_screen.json').is_file():
        from finarch.dataset.viewer.reports.response_screen import view
        return view(bundle)
    if (bundle/'quality_scope.json').is_file():
        from finarch.dataset.viewer.reports.quality_report import view
        return view(bundle)
    if (bundle/'01-preparation').is_dir():
        target=bundle/'01-preparation'
        external_labels = result_external_index(bundle)
        evaluate = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['evaluate']).evaluate
        snapshot = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['snapshot']).snapshot
        gate=viewer_review_gate(bundle) if not detail_only and (bundle/'input-selection.json').is_file() else None
        generation=bundle/'02-generation'
        from finarch.dataset.viewer.preparation_paths import round_names, select_round, feedback_sources
        generation_rounds=sorted(p.name for p in generation.glob('*-round') if p.is_dir() and not p.is_symlink())
        cases=([batch_path(target,case_name)] if detail_only else
               [p for p in sorted(target.glob('test-*')) if p.is_dir() and not p.is_symlink()])
        preparation_rounds=sorted({r for case in cases for r in round_names(case)})
        rounds=sorted(set(preparation_rounds+generation_rounds))
        selected=round_name or (rounds[-1] if rounds else None)
        if selected and selected not in rounds:
            # A selected case can reuse round 1 while the batch is on round 3.
            from finarch.dataset.viewer.preparation_paths import ROUND
            if not detail_only or not ROUND.fullmatch(selected):raise ValueError('UNKNOWN_ROUND')
        selected_case=case_name if any(p.name==case_name for p in cases) else (cases[0].name if cases else None)
        runs=[]
        for case in cases:
            if not case.is_dir() or case.is_symlink():continue
            if case.name!=selected_case:
                compact=compact_preparation_case(case,selected)
                compact['external_knowledge']=external_labels.get(case.name)
                runs.append(compact);continue
            case_root=case
            case, actual_round=select_round(case_root,selected,read_optional(case_root/'run.json'))
            if case is None:
                compact=compact_preparation_case(case_root,selected)
                compact['external_knowledge']=external_labels.get(case_root.name)
                runs.append(compact);continue
            item=collect(case,allow_partial=True,artifact_filter=artifact_filter)
            item['external_knowledge']=external_labels.get(case_root.name)
            item['list_entry']=compact_preparation_case(case_root,selected)
            item.update(case_path=str(case_root),round=actual_round,requested_round=selected,preparation_list=preparation_list_metadata(case_root),
                        carried_round=bool(actual_round and actual_round!=selected))
            item['layout']='preparation-generation-v1'
            artifacts=item['artifacts']
            item['feedback_sources']=feedback_sources(case_root,artifacts)
            view=dict(artifacts)
            view['00-data-preparation/01-select-input/01-input.json']=artifacts.get('data.json') or artifacts.get('01-source/01-receive-input/01-input.json',{})
            view['00-data-preparation/02-record-source/01-provenance.json']=artifacts.get('01-source/02-record-source/01-provenance.json')
            view['02-calculation/02-prepare-code/03-program.json']=artifacts.get('03-calculation/02-prepare-code/03-program.json') or (artifacts.get('03-calculation/01-LLM-generate-code/03-result.json') or {}).get('data')
            program=view['02-calculation/02-prepare-code/03-program.json']
            if program and isinstance(program.get('facts'),list):
                view['02-calculation/02-prepare-code/03-program.json']={**program,'facts':{f['id']:{k:v for k,v in f.items() if k!='id'} for f in program['facts']}}
            item.update(enrich(view))
            item['artifact_aliases']['00-data-preparation/01-select-input/01-input.json']='01-source/01-receive-input/01-input.json'
            try:
                snapshot(case_root)
                item['approval_blocker']=None
            except (ValueError,OSError,KeyError) as error:
                item['approval_blocker']=str(error)
            item.update(generation_view(generation,generation_rounds,selected,case_root.name,artifact_filter=artifact_filter,final_only=final_only))
            runs.append(item)
        if detail_only:
            payload={'format':'fin-arch-viewer-v1','detail_only':True,
                     'batch':{'name':name,'round':selected},'runs':runs}
            payload['revision']=hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            return payload
        completion = __import__('finarch.dataset.viewer.reports.completion_report',fromlist=['view']).view(bundle, gate=gate)
        failure_counts={phase:sum(next((c['status'] for c in reversed(row['rounds']) if c['status']!='NOT_RUN'),None)=='FAIL'
                                  for row in completion[phase]['rows']) for phase in ('preparation','generation')}
        payload={'format':'fin-arch-viewer-v1','batch':{'name':name,'layout':'preparation-generation-v1',
                 'failure_analysis':__import__('finarch.dataset.90-operations.failure_analysis',fromlist=['overview']).overview(bundle, counts=failure_counts),
                 'rechecks':__import__('finarch.dataset.90-operations.failed_recheck',fromlist=['overview']).overview(bundle, counts=failure_counts),
                 'summary':read_optional(target/'summary.json'),'readme':read_optional(bundle/'README.md'),
                 'interruption':read_optional(bundle/'interruption.json'),
                 'execution_progress':read_optional(bundle/'execution-progress.json'),
                 'preparation_failure_report':read_optional(target/'failure-report.json'),
                 'preparation_repair_results':read_optional(target/'repair-history/results.json'),
                 'failure_workbook':(bundle/'failure-review'/(bundle.name.rsplit('-',1)[-1]+'-failure-review.xlsx')).is_file(),
                 'preparation_queue':read_optional(target/'queue.json'),
                 'generation_queue':read_optional(generation/selected/'queue.json') if selected else None,
                 'generation_overview':generation_overview(generation,generation_rounds,selected),
                 # Detailed report rows are already loaded by /api/phase-report on demand.
                 'result_report':{'status':completion['status'],'on_demand':True},
                 'generated_dataset':(PROJECT/'data/generated'/name/'manifest.json').is_file(),
                 'timing_report':read_optional(bundle/'timing-report.json'),
                 'resource_history':read_optional(bundle/'resource-history.json'),
                 'completion_report':{'status':completion['status'],**{phase:{key:completion[phase][key] for key in ('unit','rounds','runtime')} for phase in ('preparation','generation')}},
                 'rounds':rounds,'round':selected,'preparation_rounds':preparation_rounds,'generation_rounds':generation_rounds,
                 'review_gate':{k:v for k,v in gate.items() if k!='approved_inputs'} if gate else None,
                 'generation_summary':read_generation_summary(generation/'summary.json'),
                 'generation_result_report':read_optional(generation/'result-report.json'),
                 'generation_timing':read_optional(generation/'timing.json'),
                 'generation_interruption':read_optional(generation/'interruption.json'),
                 'generation_feedback':{str(p.relative_to(generation/'feedback')):read_optional(p) for p in (generation/'feedback').glob('*/*.json')},
                 'round_reports':{r:{**v,'failures':[{k:x.get(k) for k in ('case','label','reason','status')} for x in v.get('failures',[])]} for r in rounds for v in [read_optional(generation/r/'final-validator.json') or {}]}},'runs':runs}
        payload['revision']=hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        return payload
    rounds=sorted(p.name for p in bundle.glob('0[123]-round') if p.is_dir() and not p.is_symlink())
    selected=round_name or (rounds[-1] if rounds else None)
    target=batch_path(bundle,selected) if selected else bundle
    case_roots={p.parent for pattern in ('run.json','events.jsonl') for p in target.glob('*/'+pattern)
                if p.parent.parent==target and not p.is_symlink() and p.resolve().is_relative_to(target.resolve())
                and not any(a.is_symlink() for a in p.parents if a.is_relative_to(target))}
    selected_case=case_name if case_name and any(p.name==case_name for p in case_roots) else (min(case_roots).name if case_roots else None)
    states={}
    if case_name is not None and rounds:
        from finarch.dataset.viewer.reports.comparison_report import outcomes
        states=outcomes(bundle,selected)
    payload={'format':'fin-arch-viewer-v1', 'batch':{'name':name,
             'summary':read_optional(target/'summary.json'), 'progress':read_optional(target/'production-progress.json') or read_optional(target/'progress.json'),
             'rounds':rounds,'round':selected,'round_failures':round_failure_counts(bundle) if rounds else [],'loop':read_optional(bundle/'loop-summary.json'),
             'result_report':result_report(bundle) if rounds else None,
             'comparison_report':read_optional(bundle/'comparison-report.json'),
             'failure_workbook':(bundle/'failure-review/012-failure-review.xlsx').is_file(),
             'timing_report':read_optional(bundle/'timing-report.json'),
                 'resource_history':read_optional(bundle/'resource-history.json'),
             'project_timing':[{'run_id':p.parent.name,'total':read_optional(p).get('total',{})}
                               for p in sorted(Path(root).glob('*/timing-report.json')) if not p.is_symlink()],
             'validator':read_optional(target/'05-text/03-final-validator/03-result.json'),
             'feedback':{str(p.relative_to(bundle)):read_optional(p) for p in (bundle/'feedback').glob('*/*.json')},
             'plan':read_optional(target/'plan.json'), 'readme':read_optional(target/'README.md') or read_optional(bundle/'README.md')},
             'runs':[compact_case(p,states) if case_name is not None and p.name!=selected_case else collect(p,allow_partial=True) for p in sorted(case_roots)]}
    for run in payload['runs']:
        run['round']=selected
        if not run.get('summary_only'):run.update(enrich(run['artifacts']))
    # VW-POT: adapt existing POT artifacts to the shared Preparation UI in memory.
    if (payload['batch'].get('plan') or {}).get('stop_after') == 'pot':
        payload['batch']['layout']='preparation-generation-v1'
        for run in payload['runs']:
            run['layout']='preparation-generation-v1'
            if run.get('summary_only'):continue
            artifacts=run['artifacts']
            aliases=run.setdefault('artifact_aliases',{})
            for original,value in list(artifacts.items()):
                if original.startswith('02-calculation/'):
                    display=original.replace('02-calculation/','03-calculation/',1)
                elif original.startswith('00-data-preparation/'):
                    display=original.replace('00-data-preparation/','01-source/',1).replace('/01-select-input/','/01-receive-input/')
                else:continue
                artifacts[display]=value
                aliases[display]=original
            run['approval_blocker']='POT_ONLY_NOT_EXECUTED_OR_COMPARED'
    payload['revision']=hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return payload


def live_events(root, name):
    """VL03: lightweight original JSONL stream, including unfinished spans."""
    target=batch_path(root,name);events=[];damaged=[]
    for path in sorted(target.rglob('events.jsonl')):
        if path.is_symlink() or path.parent.is_symlink():continue
        for number,line in enumerate(path.read_text().splitlines(),1):
            if not line.strip():continue
            try:entry=json.loads(line)
            except ValueError:
                damaged.append({'case':path.parent.name,'line':number,'reason':'partial_or_invalid_line'});continue
            events.append({**entry,'case':str(path.parent.relative_to(target)),'source':str(path.relative_to(target)),'source_line':number})
    reviews={}
    for path in sorted(target.glob('test-*/06-human-review/03-result.json')):
        if path.is_symlink() or any(p.is_symlink() for p in path.parents if p.is_relative_to(target)):continue
        items=read_optional(path)
        if isinstance(items,list):
            reviews[path.parents[1].name]={'ready':sum(v.get('status')=='AWAITING_HUMAN' for v in items),
                'total':len(items),'failed':sum(v.get('status')=='FAIL' for v in items),
                'unassessed':sum(v.get('status')=='NOT_EVALUATED' for v in items)}
    progress=read_optional(target/'production-progress.json')
    rounds=sorted(target.glob('0[123]-round'))
    if rounds:
        latest=rounds[-1]
        progress=read_optional(latest/'production-progress.json') or {'status':'CALCULATING','cases':{}}
        progress={**progress,'round':latest.name,'cases':{latest.name+'/'+key:value for key,value in progress.get('cases',{}).items()}}
    return {'run':name,'progress':progress,
            'events':events,'damaged':damaged,'reviews':reviews}


def log_detail(root,name,case_name,line_number):
    """VL04: exact event, its own saved audit, and same-parent follow-up artifact."""
    batch=batch_path(root,name);case=batch
    for component in case_name.split('/'):case=batch_path(case,component)
    log=case/'events.jsonl'
    if log.is_symlink():raise ValueError('INVALID_LOG')
    lines=log.read_text().splitlines()
    if not 1<=line_number<=len(lines):raise ValueError('INVALID_EVENT_LINE')
    event=json.loads(lines[line_number-1]);parent=event.get('parent_call_id') or event.get('call_id')
    result={'event':event,'source':str(log.relative_to(batch)),'source_line':line_number,'following_artifact':None,'audit_artifact':None}
    if event.get('phase')=='END' and event.get('call_id'):
        for raw in reversed(lines[:line_number-1]):
            try:entry=json.loads(raw)
            except ValueError:continue
            if entry.get('call_id')!=event['call_id']:continue
            if entry.get('phase')=='START':break
            if entry.get('phase')!='ARTIFACT' or not entry.get('path','').endswith('/03-result.json'):continue
            path=case/entry['path']
            if (path.resolve().is_relative_to(case.resolve()) and not path.is_symlink()
                and not any(p.is_symlink() for p in path.parents if p.is_relative_to(case))
                and path.is_file() and path.stat().st_size<=300000):
                result['audit_artifact']={'path':entry['path'],'content':read_optional(path),
                    'relationship':'same call, saved before this END event'}
            break
    if not parent:return result
    for line in lines[line_number:]:
        try:entry=json.loads(line)
        except ValueError:continue
        if entry.get('phase')=='END' and entry.get('call_id')==parent:break
        if entry.get('phase')!='ARTIFACT' or entry.get('call_id')!=parent:continue
        path=case/entry.get('path','')
        if (not path.resolve().is_relative_to(case.resolve()) or path.is_symlink()
            or any(p.is_symlink() for p in path.parents if p.is_relative_to(case))):break
        if path.is_file() and path.stat().st_size<=300000:
            result['following_artifact']={'path':entry['path'],'content':read_optional(path),
                'relationship':'same span, first subsequent saved artifact; not a separate failure verdict'}
        break
    return result


def save_preparation_review(bundle, payload):
    """Save an explicit human decision against the exact viewed artifacts."""
    record_decision = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['record_decision']).record_decision
    evaluate = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['evaluate']).evaluate
    case=batch_path(bundle/'01-preparation',payload['case'])
    review=payload['review']
    if not isinstance(review,dict):raise ValueError('INVALID_REVIEW')
    if not isinstance(review.get('reason',''),str):raise ValueError('INVALID_REVIEW_REASON')
    from finarch.dataset.viewer.preparation_paths import select_round
    active, actual_round=select_round(case,report=read_optional(case/'run.json'))
    if payload.get('round') and payload['round']!=actual_round:
        raise ValueError('REVIEW_REQUIRES_ACTIVE_ROUND')
    if review.get('snapshot_sha256') != collect(active,allow_partial=True)['snapshot_sha256']:
        raise ValueError('REVIEW_SNAPSHOT_CHANGED')
    decision=record_decision(case,review['decision'],review['reviewer'],review.get('reason',''),checklist=review.get('checklist'),allow_failed_review=True)
    return {'decision':decision,'review_gate':evaluate(bundle)}


def save_generation_review(bundle,payload):
    from datetime import datetime
    read = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['read']).read
    write = __import__('finarch.dataset.90-operations.preparation_gate', fromlist=['write']).write
    target=batch_path(batch_path(batch_path(bundle/'02-generation',payload['round']),payload['case']),payload['variant'])
    review=payload['review']
    if review.get('decision') not in ('APPROVED','REJECTED','PENDING'):raise ValueError('INVALID_DECISION')
    if not isinstance(review.get('reviewer'),str) or not review['reviewer'].strip():raise ValueError('REVIEWER_REQUIRED')
    if not isinstance(review.get('reason',''),str):raise ValueError('INVALID_REASON')
    if review['decision'] in ('REJECTED','PENDING') and not review.get('reason','').strip():raise ValueError('REVIEW_REASON_REQUIRED')
    fingerprint=collect(target,allow_partial=True)['snapshot_sha256']
    if review.get('snapshot_sha256')!=fingerprint:raise ValueError('REVIEW_SNAPSHOT_CHANGED')
    review_path=target/'05-human-review/01-result.json'
    if not review_path.exists():review_path=target/'04-human-review/01-result.json'
    result=read(review_path)
    value={**review,'automatic_status':result.get('automatic_status'),'recorded_at':datetime.now().astimezone().isoformat()}
    directory=target/'05-human-review/02-record-decision';directory.mkdir(parents=True,exist_ok=True)
    with (directory/'history.jsonl').open('a') as stream:stream.write(json.dumps(value,ensure_ascii=False)+'\n')
    write(directory/'decision.json',value)
    return {'decision':value}


def handler_for(root):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            from finarch.dataset.viewer.build import record_decisions
            if self.headers.get('Host','').split(':')[0] not in ('127.0.0.1','localhost') or urlsplit(self.path).path not in ('/api/review','/api/recheck','/api/failure-analysis','/api/evaluation-export','/api/original-export','/api/annotation/refresh','/api/annotation/import','/api/annotation/manager-review'):
                self.send_error(403);return
            origin=self.headers.get('Origin')
            if origin not in (f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'):
                self.send_error(403);return
            try:
                size=int(self.headers.get('Content-Length','0'))
                route_path=urlsplit(self.path).path
                limit=40*1024*1024 if route_path=='/api/annotation/import' else 1000000 if route_path=='/api/evaluation-export' else 100000
                if not 0<size<=limit:raise ValueError('INVALID_REVIEW_SIZE')
                payload=json.loads(self.rfile.read(size))
                if route_path=='/api/original-export':
                    from finarch.dataset.viewer.original_export import build as original_build
                    body,info=original_build(root,payload.get('run'),payload.get('view'))
                    self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8')
                    self.send_header('Content-Disposition','attachment; filename="original.html"')
                    self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
                if urlsplit(self.path).path=='/api/evaluation-export':
                    from finarch.dataset.viewer.evaluation_export import build
                    body,info=build(root,payload.get('runs'),payload.get('view'))
                    self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8')
                    self.send_header('Content-Disposition','attachment; filename="evaluation.html"')
                    self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
                if route_path.startswith('/api/annotation/'):
                    from finarch.dataset.viewer.annotation.store import refresh, upload
                    annotation_root=PROJECT/'annotation'
                    if route_path.endswith('/manager-review'):
                        from finarch.dataset.viewer.annotation.reviews import save
                        result=save(annotation_root,payload)
                    else:
                        result=upload(annotation_root,payload['date'],payload['files']) if route_path.endswith('/import') else refresh(annotation_root,payload['date'])
                    body=json.dumps(result,ensure_ascii=False).encode();self.send_response(200)
                    self.send_header('Content-Type','application/json; charset=utf-8')
                    self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
                batch=batch_path(root,payload['run'])
                if urlsplit(self.path).path=='/api/failure-analysis':
                    launch = __import__('finarch.dataset.90-operations.failure_analysis', fromlist=['launch']).launch
                    result=launch(batch,payload['phase'],payload['preview_id'])
                elif urlsplit(self.path).path=='/api/recheck':
                    launch = __import__('finarch.dataset.90-operations.failed_recheck', fromlist=['launch']).launch
                    result=launch(batch,payload['phase'])
                elif (batch/'01-preparation').is_dir():
                    result=save_generation_review(batch,payload) if payload.get('variant') else save_preparation_review(batch,payload)
                else:
                    if payload.get('round'):batch=batch_path(batch,payload['round'])
                    case=batch_path(batch,payload['case'])
                    result=record_decisions(case,payload['review'])
                body=json.dumps(result,ensure_ascii=False).encode();self.send_response(200)
            except (ValueError,KeyError,TypeError) as error:
                body=json.dumps({'error':str(error)},ensure_ascii=False).encode();self.send_response(400)
            self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)

        def do_GET(self):
            # Only loopback browser requests; no arbitrary file serving or mutations.
            if self.headers.get('Host','').split(':')[0] not in ('127.0.0.1','localhost'):
                self.send_error(403);return
            route=urlsplit(self.path)
            try:
                if route.path in ('/','/index.html','/dataset','/dataset/','/dataset/index.html'):
                    body=TEMPLATE.read_text().replace('__FINARCH_DATA__', '{"format":"fin-arch-viewer-v1","live":true,"runs":[]}').encode()
                    content_type='text/html; charset=utf-8'
                elif route.path in ('/i18n.js', '/i18n.css'):
                    body=(PROJECT/'viewer/shared'/route.path.rsplit('/',1)[1]).read_bytes()
                    content_type='text/javascript; charset=utf-8' if route.path.endswith('.js') else 'text/css; charset=utf-8'
                elif route.path == '/ea-inverse':
                    body=(PROJECT/'viewer/dataset/ea-inverse.html').read_bytes();content_type='text/html; charset=utf-8'
                elif route.path == '/ea-inverse/comparison':
                    from finarch.dataset.viewer.ea_inverse_comparison import render
                    query=parse_qs(route.query)
                    body=render(PROJECT,query.get('comparison',[None])[0]);content_type='text/html; charset=utf-8'
                elif route.path in ('/api/ea-inverse/export','/ea-inverse/annotator'):
                    from finarch.dataset.viewer.ea_inverse_export import render
                    query=parse_qs(route.query)
                    run=query.get('run',[''])[0]
                    body=render(PROJECT,run,query.get('file',[''])[0]);content_type='text/html; charset=utf-8'
                    if route.path.endswith('/export'):
                        self.send_response(200)
                        self.send_header('Content-Type',content_type)
                        self.send_header('Content-Disposition','attachment; filename="'+run+'-ea-inverse-annotator.html"')
                        self.send_header('Cache-Control','no-store')
                        self.send_header('X-Content-Type-Options','nosniff')
                        self.send_header('Content-Length',str(len(body)))
                        self.end_headers();self.wfile.write(body);return
                elif route.path in ('/api/ea-inverse/catalog','/api/ea-inverse'):
                    from finarch.dataset.viewer.ea_inverse import catalog, view
                    query=parse_qs(route.query)
                    result=catalog(PROJECT) if route.path.endswith('/catalog') else view(PROJECT,
                        query.get('run',[''])[0],query.get('file',[''])[0],query.get('case',[None])[0],query.get('type',[None])[0])
                    body=json.dumps(result,ensure_ascii=False).encode();content_type='application/json; charset=utf-8'
                elif route.path in ('/annotation','/annotation/','/annotation/index.html'):
                    body=(PROJECT/'viewer/dataset/annotation/index.html').read_bytes();content_type='text/html; charset=utf-8'
                elif route.path in ('/annotation/manager.js','/annotation/reviews.js','/annotation/style.css'):
                    body=(PROJECT/'viewer/dataset/annotation'/route.path.rsplit('/',1)[1]).read_bytes()
                    content_type='text/javascript; charset=utf-8' if route.path.endswith('.js') else 'text/css; charset=utf-8'
                elif route.path == '/api/annotation/catalog':
                    from finarch.dataset.viewer.annotation.store import comparison_catalog
                    body=json.dumps(comparison_catalog(PROJECT/'annotation'),ensure_ascii=False).encode();content_type='application/json; charset=utf-8'
                elif route.path == '/api/annotation':
                    from finarch.dataset.viewer.annotation.store import view
                    query=parse_qs(route.query)
                    included=query.get('file') if 'file' in query else None
                    result=view(PROJECT/'annotation',query.get('date',[None])[0],included)
                    body=json.dumps(result,ensure_ascii=False).encode();content_type='application/json; charset=utf-8'
                elif route.path == '/api/annotation/file':
                    from finarch.dataset.viewer.annotation.store import file_data
                    query=parse_qs(route.query)
                    body,filename=file_data(PROJECT/'annotation',query.get('date',[''])[0],query.get('id',[''])[0],query.get('kind',['repaired'])[0])
                    content_type='application/json; charset=utf-8'
                elif route.path == '/api/annotation/evidence':
                    from finarch.dataset.viewer.evaluation_export import keep_artifact
                    query=parse_qs(route.query)
                    result=batch_data(root,query.get('run',[''])[0],query.get('round',[None])[0],query.get('case',[''])[0],detail_only=True,artifact_filter=keep_artifact)
                    body=json.dumps(result,ensure_ascii=False).encode();content_type='application/json; charset=utf-8'
                elif route.path == '/api/annotation/g02':
                    from finarch.dataset.viewer.annotation.store import g02_links
                    query=parse_qs(route.query)
                    included=query.get('file') if 'file' in query else None
                    result=g02_links(PROJECT/'annotation',query.get('date',[None])[0],query.get('group',[''])[0],query.get('case',[''])[0],included)
                    body=json.dumps(result,ensure_ascii=False).encode();content_type='application/json; charset=utf-8'
                elif route.path in ('/api/annotation/review-files','/api/annotation/review-export'):
                    from finarch.dataset.viewer.annotation.reviews import export_files, zip_export
                    query=parse_qs(route.query)
                    result=export_files(PROJECT/'annotation',query.get('date',[''])[0],query.get('group',[''])[0],query.get('file') if 'file' in query else None,query.get('revision',[None])[0])
                    if route.path.endswith('/review-export'):
                        body=zip_export(result);content_type='application/zip'
                        self.send_response(200)
                        self.send_header('Content-Type',content_type)
                        self.send_header('Content-Disposition','attachment; filename="annotation-'+result['date']+'-reviews.zip"')
                        self.send_header('Cache-Control','no-store')
                        self.send_header('X-Content-Type-Options','nosniff')
                        self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
                    body=json.dumps(result,ensure_ascii=False).encode();content_type='application/json; charset=utf-8'
                elif route.path.startswith(('/dashboard', '/api/dashboard/')):
                    self.send_response(302)
                    self.send_header('Location', 'http://127.0.0.1:8895' + self.path)
                    self.send_header('Cache-Control', 'no-store')
                    self.end_headers()
                    return
                elif route.path in ('/experiments.js','/experiments/experiments.js'):
                    body=(PROJECT/'viewer/experiments/experiments.js').read_bytes();content_type='text/javascript; charset=utf-8'
                elif route.path == '/documentation-mermaid.js':
                    body=(PROJECT/'viewer/dataset/vendor/mermaid.min.js').read_bytes();content_type='text/javascript; charset=utf-8'
                elif route.path == '/contract':
                    body=(PROJECT/'viewer/dataset/contract.html').read_bytes();content_type='text/html; charset=utf-8'
                elif route.path == '/api/experiment-contract':
                    from finarch.experiments.viewer.contract_view import read_contract, list_contract_sources
                    source=parse_qs(route.query).get('source',['current'])[0]
                    result=read_contract(PROJECT,source)
                    result['available_sources']=list_contract_sources(PROJECT)
                    body=json.dumps(result,ensure_ascii=False).encode();content_type='application/json; charset=utf-8'
                elif route.path.startswith('/api/experiments/'):
                    from finarch.experiments.viewer.viewer import view as experiments_view
                    body=json.dumps(experiments_view(route.path,parse_qs(route.query)),ensure_ascii=False).encode();content_type='application/json; charset=utf-8'
                elif route.path in ('/api/generated','/api/generated-file'):
                    from importlib import import_module
                    archive=import_module('finarch.dataset.03-release.publication.consolidate')
                    query=parse_qs(route.query);name=query.get('name',[''])[0]
                    batch_path(root,name)
                    folder=batch_path(PROJECT/'data/generated',name)
                    result=archive.view(folder,query.get('case',[None])[0])
                    if route.path=='/api/generated-file':
                        body=(folder/'dataset.jsonl').read_bytes()
                        manifest=read_optional(folder/'manifest.json')
                        if hashlib.sha256(body).hexdigest()!=manifest['files']['dataset.jsonl']['sha256']:
                            raise ValueError('GENERATED_DATA_HASH_MISMATCH')
                        self.send_response(200)
                        self.send_header('Content-Type','application/x-ndjson; charset=utf-8')
                        self.send_header('Content-Disposition','attachment; filename="'+name+'-dataset.jsonl"')
                        self.send_header('Cache-Control','no-store')
                        self.send_header('Content-Length',str(len(body)))
                        self.end_headers();self.wfile.write(body);return
                    body=json.dumps(result,ensure_ascii=False).encode();content_type='application/json; charset=utf-8'
                elif route.path == '/api/token-charts':
                    from finarch.dataset.viewer.reports.token_charts import build
                    query=parse_qs(route.query)
                    result=build(batch_path(root,query.get('name',[''])[0]),query.get('phase',['preparation'])[0])
                    body=json.dumps(result,ensure_ascii=False).encode();content_type='application/json; charset=utf-8'
                elif route.path in ('/api/phase-report','/api/phase-workbook'):
                    from finarch.dataset.viewer.reports.phase_report import view, workbook, source_signature
                    query=parse_qs(route.query);bundle=batch_path(root,query.get('name',[''])[0]);phase=query.get('phase',['preparation'])[0]
                    if route.path=='/api/phase-report':
                        body=json.dumps(view(bundle,phase),ensure_ascii=False).encode();content_type='application/json; charset=utf-8'
                    else:
                        saved=bundle/'phase-reports'/phase/(phase+'-report.xlsx')
                        current=read_optional(saved.parent/'data.json') or {}
                        fresh=current.get('source_signature')==source_signature(bundle,phase)
                        body=(saved if saved.exists() and fresh else workbook(bundle,phase)).read_bytes();content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                elif route.path == '/api/failure-analysis/preview':
                    preview = __import__('finarch.dataset.90-operations.failure_analysis', fromlist=['preview']).preview
                    query=parse_qs(route.query)
                    result=preview(batch_path(root,query.get('name',[''])[0]),query.get('phase',[''])[0])
                    body=json.dumps(result,ensure_ascii=False).encode();content_type='application/json; charset=utf-8'
                elif route.path == '/live':
                    body=(TEMPLATE.parent/'live.html').read_bytes();content_type='text/html; charset=utf-8'
                elif route.path == '/logs':
                    body=(TEMPLATE.parent/'logs.html').read_bytes();content_type='text/html; charset=utf-8'
                elif route.path == '/api/purpose-log-runs':
                    from finarch.dataset.viewer.run_logs import list_runs
                    body=json.dumps(list_runs(PROJECT/'log')).encode();content_type='application/json; charset=utf-8'
                elif route.path == '/api/purpose-log-files':
                    from finarch.dataset.viewer.run_logs import list_files
                    body=json.dumps(list_files(PROJECT/'log',parse_qs(route.query).get('run',[''])[0]),ensure_ascii=False).encode();content_type='application/json; charset=utf-8'
                elif route.path == '/api/purpose-log':
                    from finarch.dataset.viewer.run_logs import read_log
                    query=parse_qs(route.query)
                    result=read_log(PROJECT/'log',query.get('run',[''])[0],query.get('file',['default.log'])[0],int(query.get('offset',['0'])[0]))
                    body=json.dumps(result,ensure_ascii=False).encode();content_type='application/json; charset=utf-8'
                elif route.path == '/api/live':
                    name=parse_qs(route.query).get('name',[''])[0]
                    body=json.dumps(live_events(root,name),ensure_ascii=False).encode();content_type='application/json; charset=utf-8'
                elif route.path == '/api/log-detail':
                    query=parse_qs(route.query)
                    detail=log_detail(root,query.get('name',[''])[0],query.get('case',[''])[0],int(query.get('line',['0'])[0]))
                    body=json.dumps(detail,ensure_ascii=False).encode();content_type='application/json; charset=utf-8'
                elif route.path == '/api/runs':
                    body=json.dumps(list_batches(root),ensure_ascii=False).encode();content_type='application/json; charset=utf-8'
                elif route.path == '/api/documentation':
                    from finarch.dataset.viewer.reports.documentation import read_document
                    query=parse_qs(route.query)
                    result=read_document(batch_path(root,query.get('run',[''])[0]),query.get('path',[''])[0])
                    body=json.dumps(result,ensure_ascii=False).encode();content_type='application/json; charset=utf-8'
                elif route.path == '/api/quality-source':
                    from finarch.dataset.viewer.reports.quality_report import source
                    query=parse_qs(route.query)
                    body=source(batch_path(root,query.get('name',[''])[0]),query.get('path',[''])[0])
                    content_type='text/plain; charset=utf-8'
                elif route.path == '/api/failure-workbook':
                    name=parse_qs(route.query).get('run',[''])[0]
                    batch=batch_path(root,name)
                    body=(batch/'failure-review'/(batch.name.rsplit('-',1)[-1]+'-failure-review.xlsx')).read_bytes()
                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                # [VP02] docs/55-viewer-speed-and-phi-two.md — conditional compressed transport.
                elif route.path == '/api/run':
                    name=parse_qs(route.query).get('name',[''])[0]
                    query = parse_qs(route.query)
                    selected_round = query.get('round',[None])[0]
                    selected_case = query.get('case',[None])[0]
                    compressed = 'gzip' in self.headers.get('Accept-Encoding','')
                    body = encode(batch_data(root,name,selected_round,selected_case,detail_only=query.get('detail_only',['0'])[0]=='1' and selected_case is not None))
                    tag = '"' + hashlib.sha256(body).hexdigest() + '"'
                    self.send_response(304 if self.headers.get('If-None-Match') == tag else 200)
                    self.send_header('ETag',tag)
                    self.send_header('Cache-Control','private, no-cache')
                    self.send_header('Vary','Accept-Encoding')
                    self.send_header('X-Content-Type-Options','nosniff')
                    if self.headers.get('If-None-Match') == tag:
                        self.end_headers();return
                    if compressed:body = gzip.compress(body,compresslevel=1,mtime=0)
                    self.send_header('Content-Type','application/json; charset=utf-8')
                    if compressed:self.send_header('Content-Encoding','gzip')
                    self.send_header('Content-Length',str(len(body)))
                    self.end_headers();self.wfile.write(body);return
                elif route.path == '/api/realization-prompt':
                    axis = parse_qs(route.query).get('axis', [''])[0]
                    definition = describe_prompt(axis)
                    definition['scope'] = 'Current instructions only; not a saved model call or generated result.'
                    body=json.dumps(definition,ensure_ascii=False).encode();content_type='application/json; charset=utf-8'
                elif route.path == '/api/audit-prompt':
                    axis = parse_qs(route.query).get('axis', [''])[0]
                    definition = describe_audit_prompt(axis)
                    definition['scope'] = 'Current audit instructions only; not a saved model call or verdict.'
                    body=json.dumps(definition,ensure_ascii=False).encode();content_type='application/json; charset=utf-8'
                elif route.path == '/api/schema':
                    # [VS01] Only registered response definitions; never arbitrary filesystem paths.
                    name=parse_qs(route.query).get('name',[''])[0]
                    if resolve_schema_id(name) not in CONTRACTS or not name.endswith('.response'):
                        raise ValueError('UNKNOWN_RESPONSE_SCHEMA')
                    definition=describe(resolve_schema_id(name))
                    from finarch.dataset.schemas.registry import schema_filename
                    definition['file']='src/finarch/dataset/schemas/json/'+schema_filename(name)
                    definition['scope']='current definition; not proof this schema was sent in the selected run'
                    body=json.dumps(definition,ensure_ascii=False).encode();content_type='application/json; charset=utf-8'
                elif route.path == '/api/knowledge-review':
                    candidates=[]
                    for directory in RUNS.iterdir():
                        if directory.is_dir() and not directory.is_symlink():
                            config=read_optional(directory/'config.json') or {}
                            if config.get('workflow')=='knowledge_review':candidates.append(directory.name)
                    candidates.sort(reverse=True)
                    selected=parse_qs(route.query).get('run',[None])[0] or (candidates[0] if candidates else None)
                    if selected not in candidates:raise ValueError('UNKNOWN_KNOWLEDGE_REVIEW')
                    directory=batch_path(RUNS,selected)
                    if parse_qs(route.query).get('compact')==['1']:
                        payload=read_optional(directory/'progress.json') or {}
                    else:payload={'runs':candidates,'selected':selected,'path':str(directory),
                                     'config':read_optional(directory/'config.json'),
                                     'summary':read_optional(directory/'summary.json'),
                                     'selection':read_optional(directory/'selection.json'),
                                     'prompt':read_optional(directory/'prompt.md'),
                                     'completion_audit':read_optional(directory/'completion-audit.json'),
                                     'comparison':read_optional(directory/'comparison.json'),
                                     'api_cost':read_optional(directory/'api-cost-estimate.json'),
                                     'usage_before':read_optional(directory/'usage-before.json'),
                                     'usage_after':read_optional(directory/'usage-after.json')}
                    body=json.dumps(payload,ensure_ascii=False).encode()
                    content_type='application/json; charset=utf-8'
                elif route.path == '/api/phi-two':
                    from finarch.dataset.viewer.phi_two import load
                    query = parse_qs(route.query)
                    body = encode(load(root,query.get('run',[None])[0],query.get('case',[None])[0]))
                    content_type = 'application/json; charset=utf-8'
                elif route.path == '/api/context-screen':
                    candidates=[p for p in (PROJECT/'reports/run').iterdir() if p.is_dir() and (read_optional(p/'config.json') or {}).get('workflow')=='context_screen']
                    if not candidates:raise ValueError('No context screening run')
                    directory=max(candidates,key=lambda p:p.name)
                    records={}
                    path=directory/'decisions.jsonl'
                    if path.exists():
                        for line in path.read_text().splitlines():
                            try:
                                item=json.loads(line);records[item['source_path']]=item
                            except (ValueError,KeyError):pass
                    body=json.dumps({'progress':read_optional(directory/'progress.json'),'records':list(records.values()),'path':str(directory)},ensure_ascii=False).encode()
                    content_type='application/json; charset=utf-8'
                elif route.path == '/api/raw-knowledge':
                    directory=PROJECT/'data/raw/raw-seperate/classification'
                    records={}
                    path=directory/'decisions.jsonl'
                    if path.exists():
                        for line in path.read_text().splitlines():
                            try:
                                item=json.loads(line);records[item['source_path']]=item
                            except (ValueError,KeyError):pass
                    body=json.dumps({'progress':read_optional(directory/'progress.json'),'records':list(records.values()),'path':str(directory)},ensure_ascii=False).encode()
                    content_type='application/json; charset=utf-8'
                elif route.path == '/api/health':
                    body=json.dumps({'viewer':'dataset','project':str(PROJECT),'runs_root':str(root)}).encode();content_type='application/json'
                else: self.send_error(404);return
            except ValueError:
                self.send_error(404);return
            except OSError:
                self.send_error(503,'Results temporarily unavailable');return
            self.send_response(200)
            self.send_header('Content-Type',content_type)
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Length',str(len(body)))
            self.end_headers();self.wfile.write(body)

        def log_message(self,*args): pass
    return Handler


def main():
    from finarch.shared.viewer import serve
    serve(handler_for(RUNS), name='dataset', port=8893)


if __name__ == '__main__':
    main()
