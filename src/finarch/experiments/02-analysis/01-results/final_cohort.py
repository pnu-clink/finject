"""Pool saved experiment evidence for an immutable human-PASS release.

This entry point performs local reads and arithmetic only. It never dispatches
Evaluation or Analysis, collects provider results, or changes any source run.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
from importlib import import_module
import json
from pathlib import Path

outcomes = import_module('finarch.experiments.02-analysis.05-outcomes.semantic_answerability')
layout = import_module('finarch.experiments.90-operations.run_layout')
ROOT = Path(__file__).resolve().parents[5]
SOURCES = ('FinanceReasoning', 'TAT-QA')
MODELS = (
    ('Luna', '20261003-exp-009-concat-002-luna', '20261003-exp-004-tatqa-luna-sol-low'),
    ('Haiku', '20261003-exp-010-concat-002-haiku', '20261003-exp-005-tatqa-haiku'),
    ('Qwen3-8B', '20261003-exp-013-a100-financereasoning-qwen3-8b', '20261003-exp-012-a100-tatqa-qwen3-8b'),
    ('Qwen3-14B', '20261003-exp-015-a100-financereasoning-qwen3-14b', '20261003-exp-014-a100-tatqa-qwen3-14b'),
    ('Qwen3.8-27B', '20261003-exp-017-a100-financereasoning-qwen3-8-27b', '20261003-exp-016-a100-tatqa-qwen3-8-27b'),
    ('Gemini 3.5 Flash Lite', '20261003-exp-011-concat-002-gemini-3-5-flash-lite', '20261003-exp-008-tatqa-gemini-3-5-flash-lite'),
)
VARIANTS = ('ORIGINAL', 'IC_VALUE_01_BEFORE', 'IC_VALUE_01_AFTER',
            'IC_SOURCE_A_ONLY', 'IC_SOURCE_B_ONLY', 'IC_RELATION_01', 'EA_01', 'EA_02')
MAIN = outcomes.H1_VARIANTS
CONDITIONS = (('unguided', 'off'), ('unguided', 'on'), ('guided', 'off'), ('guided', 'on'))
CODES = ('NS', 'NU', 'AS', 'AU', 'ND', 'AD', 'F')
DETAILS = ('NU_MATCH', 'NU_MISMATCH', 'NU_UNKNOWN', 'AU_U_U', 'AU_S_U', 'AU_U_S', 'AU_D_U', 'AU_U_D')
RESOLVED = {'NS', 'NU', 'AS', 'AU'}
PAIRS = (('IC_VALUE_01_BEFORE', 'IC_SOURCE_A_ONLY'), ('IC_VALUE_01_AFTER', 'IC_SOURCE_B_ONLY'))


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def ratio(n, d):
    return n / d if d else None


def counts(rows):
    c = Counter(r['nasu'] for r in rows)
    d = Counter(r['nasu_detail'] for r in rows)
    result = {'planned': len(rows), **{k: c[k] for k in CODES},
              'details': {k: d[k] for k in DETAILS},
              'target_status': dict(Counter(r['target_status'] for r in rows)),
              'review_status': dict(Counter(r['review_status'] for r in rows)),
              'unreviewed_by_action':dict(Counter(r['action'] for r in rows if r['nasu']=='F'))}
    result.update(S=c['NS'] + c['AS'], U=c['NU'] + c['AU'], D=c['ND'] + c['AD'],
                  resolved=sum(c[k] for k in RESOLVED), reviewed=len(rows)-c['F'])
    result.update(O=ratio(result['S'], result['resolved']), N=ratio(c['NS'], c['NS']+c['NU']),
                  A=ratio(c['AS'], c['AS']+c['AU']), NS_share=ratio(c['NS'], len(rows)),
                  AS_share=ratio(c['AS'], len(rows)), coverage=ratio(result['reviewed'], len(rows)))
    assert sum(result[k] for k in CODES) == len(rows)
    assert result['S'] + result['U'] + result['D'] + result['F'] == len(rows)
    assert sum(result['details'][k] for k in DETAILS[:3]) == c['NU']
    assert sum(result['details'][k] for k in DETAILS[3:]) == c['AU']
    return result


def original_cohort(row):
    if row['target_status'] != 'VALID':
        return 'UNKNOWN'
    if row['action'] == 'A' or row['original_reference_match'] is False:
        return 'INCORRECT'
    return 'CORRECT' if row['original_reference_match'] is True else 'UNKNOWN'


def compact_state(value):
    fields = ('status','stage','requests','completed','valid','pending','statuses',
              'unresolved_trial_ids','model','reasoning_effort','completed_at','updated_at','reason')
    return {k:value[k] for k in fields if k in value}


def selection(release, connection, snap):
    families = outcomes.unique(snap.read(release / 'dataset.jsonl', lines=True), 'id')
    snap.read(connection, default=None) if connection.suffix == '.json' else None
    raw = connection.read_bytes()
    snap.files[str(connection.resolve())] = outcomes.sha256(raw).hexdigest()
    links = list(csv.DictReader(raw.decode('utf-8-sig').splitlines()))
    by_source, selected = {}, Counter()
    assert len(links) == len(families) == 1354
    for link in links:
        fid = link['final_id']
        family = families[fid]
        items = {v['type']: v for v in [family['original'], *family['variants']]}
        assert set(items) == set(VARIANTS)
        assert all(items[v]['annotation']['status'] == 'PASS' for v in VARIANTS[1:])
        key = (link['source_dataset'], link['source_case_id'])
        if key in by_source:
            raise ValueError('DUPLICATE_SELECTION:' + str(key))
        by_source[key] = (link, items)
        selected[key[0]] += 1
    assert dict(selected) == {'FinanceReasoning': 1071, 'TAT-QA': 283}
    for dataset, run in zip(SOURCES, ('20261003-concat-002', '20261003-003')):
        source = snap.read(ROOT / 'data/generated' / run / 'dataset.jsonl', lines=True)
        passed = {r['id'] for r in source if len(r.get('variants', [])) == 7
                  and all(v.get('annotation', {}).get('status') == 'PASS' for v in r['variants'])}
        expected = {case for ds, case in by_source if ds == dataset}
        assert expected == passed, ('HUMAN_PASS_SELECTION_MISMATCH', dataset)
        indexed = outcomes.unique(source, 'id')
        for case in expected:
            _, final_items = by_source[(dataset, case)]
            orig = indexed[case]
            raw_items = {v['type']: v for v in [orig['original'], *orig['variants']]}
            for variant, item in final_items.items():
                for field in ('question', 'context', 'content_sha256'):
                    assert item[field] == raw_items[variant][field], ('FINAL_SOURCE_MISMATCH', case, variant, field)
    return by_source, links


def aggregates(rows):
    keyed = {(r['model_label'], r['final_id'], r['prompt_condition'], r['reasoning'], r['variant']): r for r in rows}
    assert len(keyed) == len(rows)
    for r in rows:
        original = keyed[(r['model_label'], r['final_id'], r['prompt_condition'], r['reasoning'], 'ORIGINAL')]
        r['original_cohort'] = original_cohort(original)
    rq1, rq2, rq3, grouped, scopes, coverage = [], [], [], [], [], []
    for label, *_ in MODELS:
        model_rows = [r for r in rows if r['model_label'] == label]
        for scope, variant_set in (('all', VARIANTS), ('originals', ('ORIGINAL',)), ('variants', VARIANTS[1:]), ('h1', MAIN)):
            chosen = [r for r in model_rows if r['variant'] in variant_set]
            scopes.append({'scope': scope, 'model': label, **counts(chosen),
                           'categories': dict(Counter(r['semantic_answerability'] for r in chosen))})
        for prompt, reasoning in CONDITIONS:
            condition = [r for r in model_rows if (r['prompt_condition'], r['reasoning']) == (prompt, reasoning)]
            originals = [r for r in condition if r['variant'] == 'ORIGINAL']
            main = [r for r in condition if r['variant'] in MAIN]
            identity = {'dataset': 'FInject', 'model': label, 'G': 'ON' if prompt == 'guided' else 'OFF',
                        'R': reasoning.upper(), 'prompt_condition': prompt, 'reasoning': reasoning}
            assert len(originals) == 1354 and len(main) == 6770 and len(condition) == 43328//4
            oc = Counter(r['original_cohort'] for r in originals)
            first = identity | counts(main)
            first['TBD'] = first['reviewed'] == 0
            rq1.append(first)
            cohorts = {cohort: counts([r for r in main if r['original_cohort'] == cohort])
                       for cohort in ('CORRECT', 'INCORRECT', 'UNKNOWN')}
            rq2.append(identity | {'originals': {c: oc[c] for c in cohorts}, 'O': ratio(oc['CORRECT'],1354),
                'C': cohorts['CORRECT'], 'I': cohorts['INCORRECT'], 'unknown': cohorts['UNKNOWN'],
                'delta_pp': ((cohorts['CORRECT']['O']-cohorts['INCORRECT']['O'])*100
                    if cohorts['CORRECT']['O'] is not None and cohorts['INCORRECT']['O'] is not None else None)})
            for cohort in cohorts:
                for variant in MAIN:
                    chosen = [r for r in main if r['original_cohort'] == cohort and r['variant'] == variant]
                    grouped.append(identity | {'cohort': cohort, 'variant': variant, 'original_count': oc[cohort], **counts(chosen)})
            for number, (before, after) in enumerate(PAIRS, 1):
                paired = [(keyed[(label,fid,prompt,reasoning,before)], keyed[(label,fid,prompt,reasoning,after)])
                          for fid in {r['final_id'] for r in originals}]
                complete = [(b,a) for b,a in paired if b['nasu'] in RESOLVED and a['nasu'] in RESOLVED]
                transitions = Counter(b['nasu']+'->'+a['nasu'] for b,a in complete)
                bcount = sum(b['nasu']=='AS' for b,a in complete)
                acount = sum(a['nasu']=='AS' for b,a in complete)
                retained = transitions['AS->AS']
                omitted = Counter('F' if 'F' in (b['nasu'],a['nasu']) else 'D' for b,a in paired
                                  if b['nasu'] not in RESOLVED or a['nasu'] not in RESOLVED)
                assert sum(transitions.values())+sum(omitted.values()) == 1354
                rq3.append(identity | {'pair': number, 'before_variant':before, 'after_variant':after,
                    'planned':1354,'n':len(complete),'before':bcount,'after':acount,'retained':retained,
                    'new':acount-retained,'retention':ratio(retained,bcount),
                    'delta_pp': ((acount-bcount)/len(complete)*100 if complete else None),
                    'transitions':dict(transitions),'excluded':dict(omitted),
                    'pre_as_all':sum(b['nasu']=='AS' for b,a in paired),
                    'pre_as_to':dict(Counter(a['nasu'] for b,a in paired if b['nasu']=='AS'))})
            variant_rows = [r for r in condition if r['variant'] != 'ORIGINAL']
            coverage.append(identity | {'originals':dict(oc), 'all_items':counts(condition),
                                       'variants':counts(variant_rows), 'main':counts(main)})
    return {'format':'FInjectFinalCohortResultsV1','models':[x[0] for x in MODELS],
            'main_variants':list(MAIN),'rq1':rq1,'rq2':rq2,'rq3':rq3,
            'aggregates':grouped,'scopes':scopes,'coverage':coverage}


def build(release, connection, output):
    if output.exists():
        raise FileExistsError('Output snapshot already exists: ' + str(output))
    output.mkdir(parents=True)
    log = output/'execution.log'
    def event(kind, **details):
        line=json.dumps({'at':datetime.now(timezone.utc).isoformat(),'event':kind,**details},ensure_ascii=False)
        with log.open('a') as f: f.write(line+'\n')
        print(line,flush=True)
    snap = outcomes.Snapshot()
    selected, links = selection(release, connection, snap)
    pooled, run_info = [], []
    event('selection_verified',families=len(links),human_pass_variants=9478,new_model_calls=0)
    for label, fr, tat in MODELS:
        for dataset, run in zip(SOURCES, (fr,tat)):
            root = ROOT/'reports/experiments-run'/run
            public = outcomes.unique(snap.read(layout.inputs(root)/'public.jsonl',lines=True),'item_id')
            native, native_snap = outcomes.extract(root)
            snap.files.update(native_snap.files); snap.attempts.update(native_snap.attempts)
            native_selected = [r for r in native if (dataset,r['case']) in selected]
            config = snap.read(root/'config.json')
            models = config.get('evaluation',config)['models']
            assert len(models) == 1
            seen = set()
            for r in native_selected:
                link, items = selected[(dataset,r['case'])]
                item = items[r['variant']]
                assert all(public[r['item_id']][k]==item[k] for k in ('question','context')), ('FROZEN_INPUT_MISMATCH',run,r['item_id'])
                ident=(link['final_id'],r['prompt_condition'],r['reasoning'],r['variant'])
                assert ident not in seen
                seen.add(ident)
                compact = {k:v for k,v in r.items() if k not in ('assessment','independent_item_review','dataset')}
                pooled.append(compact | {'dataset':'FInject','model_label':label,'final_id':link['final_id'],
                    'final_item_id':item['item_id'],'source_dataset':dataset,'source_subdataset':r['dataset'],
                    'source_run':link['source_run'],'source_case_id':r['case'],
                    'configured_condition':True,'independent_item_review_present':r['independent_item_review'] is not None})
            for (ds,case),(link,items) in selected.items():
                if ds != dataset: continue
                for prompt,reasoning in CONDITIONS:
                    for variant in VARIANTS:
                        if (link['final_id'],prompt,reasoning,variant) in seen: continue
                        pooled.append({'dataset':'FInject','model_label':label,'final_id':link['final_id'],
                            'final_item_id':items[variant]['item_id'],'source_dataset':dataset,'source_run':link['source_run'],
                            'source_case_id':case,'case':case,'run':run,'variant':variant,'prompt_condition':prompt,
                            'reasoning':reasoning,'model':models[0]['key'],'target_model':models[0]['model'],
                            'configured_condition':False,'target_status':'CONDITION_NOT_RUN','review_status':'NOT_RUN',
                            'action':'UNKNOWN','answer':None,'original_reference_match':None,'nasu':'F','nasu_detail':'NOT_RUN',
                            'semantic_answerability':'UNCLASSIFIED','item_answerability':'UNDETERMINED',
                            'item_answerability_basis':'NOT_ESTABLISHED','independent_item_review_present':False})
            a02 = [p for p in native_snap.attempts if '/02_comparison/' in p and Path(p).name in {r['analysis_trial_id'] for r in native_selected if r.get('analysis_trial_id')}]
            statuses = Counter(r['target_status'] for r in native_selected)
            run_info.append({'source_dataset':dataset,'run':run,'model_label':label,
                'target_model':models[0]['model'],'reasoning_efforts':models[0].get('reasoning_efforts'),
                'selected_families':1071 if dataset=='FinanceReasoning' else 283,'stored_planned_responses':len(native_selected),
                'target_status':dict(statuses),'variant_review_status':dict(Counter(r['review_status'] for r in native_selected if r['variant']!='ORIGINAL')),
                'selected_a02_families':len(a02),'state':compact_state(snap.read(root/'state.json',default={}).get('analysis',{})),
                'a02_state':compact_state(snap.read(root/'02_analysis/02_comparison/state.json',default={}))})
            event('saved_run_read',run=run,model=label,selected=len(native_selected),status=dict(statuses))
    assert len(pooled) == 1354*32*6
    result = aggregates(pooled)
    snap.verify()
    now=datetime.now(timezone.utc).isoformat()
    result.update(generated_at=now,release=str(release.relative_to(ROOT)),sources={'FinanceReasoning':1071,'TAT-QA':283},
                  families=1354,variants=9478,items=10832,new_model_calls=0,runs=run_info)
    dump(output/'summary.json',result)
    with (output/'responses.jsonl').open('w') as f:
        for r in pooled: f.write(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
    with (output/'selection.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(links[0]));w.writeheader();w.writerows(links)
    sources={str(Path(k).relative_to(ROOT)):v for k,v in snap.files.items()}
    dump(output/'manifest.json',{'format':'FInjectSavedResultSnapshotV1','generated_at':now,'new_model_calls':0,
        'source_hashes':sources,'latest_attempts':{str(Path(k).relative_to(ROOT)):str(Path(v).relative_to(ROOT)) if v else None for k,v in snap.attempts.items()},
        'outputs':{p.name:outcomes.store.file_hash(p) for p in [output/'responses.jsonl',output/'summary.json',output/'selection.csv']},
        'verification':{'human_pass_exact_set':True,'source_final_content_equal':True,'frozen_inputs_equal':True,
                        'unique_model_final_condition_variant':True,'category_conservation':True,'source_hashes_unchanged':True}})
    template=ROOT/'src/finarch/documentation/templates/finject-final-results.md'
    (output/'README.md').write_text(template.read_text().replace('__GENERATED_AT__',now))
    event('pooled_snapshot_written',responses=len(pooled),new_model_calls=0,source_files=len(sources))
    return result


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release',type=Path,default=ROOT/'data/final/finject-20261007')
    parser.add_argument('--connection',type=Path,default=ROOT/'data/final/finject-20261007-connection-table.csv')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    build(args.release.resolve(),args.connection.resolve(),args.output.resolve())
