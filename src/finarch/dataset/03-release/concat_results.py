"""Overlay one complete source cohort in frozen result arrays; no model calls."""
import argparse
import importlib
import json
import subprocess
import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from pathlib import Path

export = importlib.import_module('finarch.dataset.03-release.export_run_results')
NAMES = ('00-input.json', *(folder + '.json' for _, folder in export.TYPES))
TEMPLATES = Path(__file__).resolve().parents[2] / 'documentation/templates'


def load(run):
    root = run / 'results'
    manifest = export.read(root / 'manifest.json')
    if manifest['source_run'] != run.name:
        raise ValueError('SOURCE_RUN_MISMATCH')
    arrays = {}
    for name in NAMES:
        if export.sha(root / name) != manifest['files'][name]['sha256']:
            raise ValueError('SOURCE_HASH_MISMATCH:' + name)
        arrays[name] = export.read(root / name)
        ids = [row['id'] for row in arrays[name]]
        if len(ids) != len(set(ids)):
            raise ValueError('DUPLICATE_ID:' + name)
    ids = [row['id'] for row in arrays[NAMES[0]]]
    for (label, _), name in zip(export.TYPES, NAMES[1:]):
        if [row['id'] for row in arrays[name]] != ids:
            raise ValueError('COMPLETE_COHORT_REQUIRED:' + name)
        if any(row['type'] != label for row in arrays[name]):
            raise ValueError('TYPE_MISMATCH:' + name)
    hashes = {name: export.sha(root / name) for name in (*NAMES, 'manifest.json')}
    return arrays, hashes


def complete_ids(arrays):
    indexes = [{item['id']: item for item in arrays[name]} for name in NAMES[1:]]
    return {row['id'] for row in arrays[NAMES[0]] if
            all(index[row['id']]['status'] == 'PASS' for index in indexes)}


def materialize_pipeline(output_run):
    """Copy the selected source histories so the unmodified stage viewer can inspect them."""
    output_run=Path(output_run).resolve()
    manifest=export.read(output_run/'results/manifest.json')
    origins=manifest['row_source_runs']
    sources={name:Path(info['path']) for name,info in manifest['sources'].items()}
    stage=output_run/'.pipeline-staging'
    stage.mkdir(exist_ok=True)
    jobs=[]
    for case,origin in origins.items():
        source=sources[origin]
        prep=source/'01-preparation'/case
        if not prep.is_dir():raise ValueError('MISSING_PREPARATION_HISTORY:'+case)
        jobs.append((prep,stage/'01-preparation'/case))
        for parent in sorted((source/'02-generation').glob('*-round')):
            generation=parent/case
            if generation.is_dir():jobs.append((generation,stage/'02-generation'/parent.name/case))
    def copy_history(pair):
        source,destination=pair
        if destination.exists():shutil.rmtree(destination)
        destination.parent.mkdir(parents=True,exist_ok=True)
        temporary=destination.with_name('.'+destination.name+'-'+uuid.uuid4().hex)
        # Commit each complete APFS clone atomically; a stopped copy is never reused.
        try:
            subprocess.run(['cp','-c','-pR',str(source),str(temporary)],check=True,capture_output=True)
            temporary.rename(destination)
        finally:
            if temporary.exists():shutil.rmtree(temporary)
    print('History copy: '+str(len(jobs))+' case directories',flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        pending=[pool.submit(copy_history,pair) for pair in jobs]
        for number,future in enumerate(as_completed(pending),1):
            future.result()
            if number%100==0 or number==len(jobs):print('History copy '+str(number)+'/'+str(len(jobs)),flush=True)
    # Merge scheduler indexes by the same source selection; keep real per-case attempts unchanged.
    prep_summaries={name:export.read(path/'01-preparation/summary.json') for name,path in sources.items()}
    results=[record for name,summary in prep_summaries.items() for record in summary.get('results',[])
             if origins.get(record['input_id'])==name]
    export.save(stage/'01-preparation/summary.json',{'status':'FINISHED','planned':len(origins),'processed':len(results),'results':results,
                'source_runs':list(sources),'scope':'Copied source histories; no new model calls.'})
    generation_rounds=[]
    for number in range(1,4):
        round_name=f'{number:02d}-round';round_results=[]
        for origin,source in sources.items():
            index=source/'01-preparation/rounds'/(round_name+'.json')
            if index.is_file():
                round_results.extend(row for row in export.read(index).get('results',[]) if origins.get(row['input_id'])==origin)
        if round_results:export.save(stage/'01-preparation/rounds'/(round_name+'.json'),{'status':'FINISHED','results':round_results})
        cases={};failures=[];round_exists=False
        for origin,source in sources.items():
            parent=source/'02-generation'/round_name
            if not parent.is_dir():continue
            round_exists=True
            progress=export.read(parent/'progress.json') if (parent/'progress.json').is_file() else {}
            cases.update({case:items for case,items in progress.get('cases',{}).items() if origins.get(case)==origin})
            validator=export.read(parent/'final-validator.json') if (parent/'final-validator.json').is_file() else {}
            failures.extend(row for row in validator.get('failures',[]) if origins.get(row['case'])==origin)
        if round_exists:
            parent=stage/'02-generation'/round_name
            export.save(parent/'progress.json',{'status':'FINISHED','cases':cases})
            verdict={'round':number,'decision':'COMPLETED_SOURCE_OVERLAY','failure_count':len(failures),'failures':failures}
            export.save(parent/'final-validator.json',verdict)
            generation_rounds.append({k:v for k,v in verdict.items() if k!='failures'})
    latest={}
    for origin,source in sources.items():
        summary=export.read(source/'02-generation/summary.json')
        latest.update({case:items for case,items in summary.get('latest',{}).items() if origins.get(case)==origin})
    export.save(stage/'02-generation/summary.json',{'status':'COMPLETED_SOURCE_OVERLAY','rounds':generation_rounds,'latest':latest,'source_runs':list(sources)})
    first=next(iter(sources.values()))
    selection=export.read(first/'input-selection.json');selection['cases']=list(origins)
    export.save(output_run/'input-selection.json',selection)
    if (first/'config.json').is_file():export.save(output_run/'config.json',export.read(first/'config.json'))
    for phase in ('01-preparation','02-generation'):
        if (output_run/phase).exists():raise ValueError('HISTORY_TARGET_ALREADY_EXISTS:'+phase)
        (stage/phase).rename(output_run/phase)
    stage.rmdir()
    evaluate=importlib.import_module('finarch.dataset.90-operations.preparation_gate').evaluate
    gate=evaluate(output_run,persist=True)
    completion=importlib.import_module('finarch.dataset.viewer.reports.completion_report').snapshot(output_run,gate=gate)
    completion['status']='COMPLETED'
    completion['scope']='Copied completed source histories; no new pipeline execution.'
    export.save(output_run/'completion-report.json',completion)
    audit=TEMPLATES.parents[3]/'log/dataset-concat'/output_run.name
    export.save(audit/'history-copy.json',{'status':'PASS','copied_case_directories':len(jobs),'source_runs':list(sources),
                'source_files_modified':False,'model_calls':0,'viewer':'Existing full Preparation/Generation stage viewer.'})
    print('Full stage histories ready',flush=True)


def concat(base_run, replacement_run, output_run, source_prefix):
    base_run, replacement_run, output_run = map(
        lambda p: Path(p).resolve(), (base_run, replacement_run, output_run))
    if output_run.exists():
        raise ValueError('NEW_OUTPUT_REQUIRED')
    if not output_run.is_relative_to(TEMPLATES.parents[3] / 'reports/run'):
        raise ValueError('OUTPUT_MUST_BE_UNDER_REPORTS_RUN')
    if not source_prefix:
        raise ValueError('SOURCE_PREFIX_REQUIRED')
    base, base_hashes = load(base_run)
    replacement, replacement_hashes = load(replacement_run)
    cohort = {r['id'] for r in base[NAMES[0]] if
              r['input']['provenance']['source_id'].startswith(source_prefix)}
    replacement_inputs = {r['id']: r for r in replacement[NAMES[0]]}
    if not cohort or set(replacement_inputs) != cohort:
        raise ValueError('REPLACEMENT_MUST_MATCH_ENTIRE_SOURCE_COHORT')
    originals = {r['id']: r for r in base[NAMES[0]]}
    raw_inputs = {}
    for run in (base_run, replacement_run):
        input_path = Path(export.read(run / 'input-selection.json')['input_path'])
        if not input_path.is_absolute():
            input_path = TEMPLATES.parents[3] / input_path
        raw_inputs[run.name] = {r['id']: r for r in export.read(input_path)}
    question_revisions = []
    for case in cohort:
        old, new = originals[case]['input'], replacement_inputs[case]['input']
        for key in ('raw_id', 'reference_answer', 'reference_answer_type',
                    'reference_precision'):
            if old[key] != new[key]:
                raise ValueError('ORIGINAL_IDENTITY_CHANGED:' + case + ':' + key)
        for key in ('raw_id', 'question', 'reference_answer', 'reference_answer_type',
                    'reference_precision'):
            if raw_inputs[base_run.name][case][key] != raw_inputs[replacement_run.name][case][key]:
                raise ValueError('RAW_INPUT_IDENTITY_CHANGED:' + case + ':' + key)
        if old['provenance']['source_id'] != new['provenance']['source_id']:
            raise ValueError('SOURCE_ID_CHANGED:' + case)
        if old['question'] != new['question']:
            question_revisions.append({'id': case, 'old_question': old['question'],
                'new_question': new['question'], 'reason': 'Saved Preparation outputs differ; retain the replacement output.'})
    merged = {}
    for name in NAMES:
        updates = {row['id']: row for row in replacement[name]}
        merged[name] = [updates[row['id']] if row['id'] in cohort else row
                        for row in base[name]]
    before, replacement_pass, after = map(complete_ids, (base, replacement, merged))
    if any(row['status'] != 'PASS' for row in merged[NAMES[0]] if row['id'] in after):
        raise ValueError('SEVEN_PASS_WITHOUT_PREPARATION_PASS')
    changes = [{'id': row['id'], 'before_all_seven_pass': row['id'] in before,
                'after_all_seven_pass': row['id'] in after,
                'source_run': replacement_run.name if row['id'] in cohort else base_run.name,
                'replaced': row['id'] in cohort}
               for row in merged[NAMES[0]]]
    summary = {'kind': 'CONSOLIDATED_RESULT_OVERLAY', 'base_run': base_run.name,
               'replacement_run': replacement_run.name, 'source_prefix': source_prefix,
               'input_count': len(merged[NAMES[0]]), 'replaced_count': len(cohort),
               'before_all_seven_pass': len(before), 'old_cohort_all_seven_pass': len(before & cohort),
               'unchanged_all_seven_pass': len(before - cohort),
               'replacement_all_seven_pass': len(replacement_pass),
               'preparation_question_difference_count': len(question_revisions),
               'after_all_seven_pass': len(after), 'net_gain': len(after) - len(before),
               'gained_count': len(after - before), 'lost_count': len(before - after),
               'gained_ids': sorted(after - before), 'lost_ids': sorted(before - after),
               'retained_pass_ids': sorted(before & after), 'all_seven_pass_ids': sorted(after),
               'model_calls': 0,
               'meaning': 'Seven automatic PASS results, not human approval or semantic correctness.'}
    sources = {base_run.name: {'path': str(base_run), 'hashes': base_hashes},
               replacement_run.name: {'path': str(replacement_run), 'hashes': replacement_hashes}}
    row_sources = {row['id']: row['source_run'] for row in changes}
    # Check source snapshots once more before committing a new dataset folder.
    for source in sources.values():
        for name, digest in source['hashes'].items():
            if export.sha(Path(source['path']) / 'results' / name) != digest:
                raise ValueError('SOURCE_CHANGED_DURING_CONCAT:' + name)
    output_run.mkdir(parents=True)
    for root, rows, policy in (
            (output_run / 'results', merged, 'ALL_INPUTS_SOURCE_COHORT_OVERLAY'),
            (output_run / 'results/all-seven-pass',
             {name: [row for row in items if row['id'] in after] for name, items in merged.items()},
             'ALL_SEVEN_VARIANTS_AUTOMATIC_PASS')):
        files = {}
        for name, items in rows.items():
            export.save(root / name, items)
            files[name] = {'count': len(items), 'sha256': export.sha(root / name),
                           'status_counts': dict(Counter(row['status'] for row in items))}
        ids = [r['id'] for r in rows[NAMES[0]]]
        export.save(root / 'manifest.json', {
            'source_run': output_run.name, 'selected_count': len(ids),
            'selection_policy': policy, 'files': files, 'sources': sources,
            'row_source_runs': {case: row_sources[case] for case in ids},
            'source_path_semantics': 'Row source/result/edit_provenance/inverse_review_ref paths are relative to row_source_runs[id], not this consolidated folder.',
            'meaning': summary['meaning'], 'model_calls': 0})
    audit_root = TEMPLATES.parents[3] / 'log/dataset-concat' / output_run.name
    audit_root.mkdir(parents=True, exist_ok=True)
    export.save(audit_root / 'concat-summary.json', summary)
    (audit_root / 'terminal.log').write_text(json.dumps(summary, ensure_ascii=False) + '\n')
    export.save(audit_root / 'case-map.json', changes)
    export.save(audit_root / 'question-revisions.json', sorted(question_revisions, key=lambda r: r['id']))
    export.save(audit_root / 'concat-log.json', {'sources': sources, 'summary': summary,
                'operation': 'REPLACE_ENTIRE_COHORT_IN_ALL_EIGHT_ARRAYS',
                'non_replaced_rows_unchanged': True, 'source_runs_modified': False,
                'pipeline_executed': False, 'model_calls': 0})
    export.save(output_run / 'run-info.json', {'display_name': output_run.name,
                'kind': summary['kind'], 'source_runs': [base_run.name, replacement_run.name]})
    values = {**summary, 'output_name': output_run.name}
    (audit_root / 'README.md').write_text((TEMPLATES / 'concat-log-readme.md').read_text().format(**values))
    for template, relative in (('concat-run-readme.md', 'README.md'),
                               ('concat-results-readme.md', 'results/README.md'),
                               ('concat-pass-readme.md', 'results/all-seven-pass/README.md')):
        (output_run / relative).write_text((TEMPLATES / template).read_text().format(**values))
    for root in (output_run / 'results', output_run / 'results/all-seven-pass'):
        manifest = export.read(root / 'manifest.json')
        for name in NAMES:
            if export.sha(root / name) != manifest['files'][name]['sha256']:
                raise ValueError('OUTPUT_HASH_MISMATCH:' + name)
    export.save(audit_root / 'validation.json', {
        'status': 'PASS', 'scope': 'Source identity, cohort alignment, output hashes and seven-PASS selection; not semantic validation.',
        'input_rows_per_file': summary['input_count'],
        'all_seven_pass_rows_per_file': summary['after_all_seven_pass'], 'model_calls': 0})
    materialize_pipeline(output_run)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-run', required=True)
    parser.add_argument('--replacement-run', required=True)
    parser.add_argument('--output-run', required=True)
    parser.add_argument('--source-prefix', required=True)
    args = parser.parse_args()
    print(json.dumps(concat(args.base_run, args.replacement_run, args.output_run,
                           args.source_prefix), ensure_ascii=False))
