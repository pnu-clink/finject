"""Package registered EA Q/C and display translations into one offline HTML."""
import hashlib
import json
from pathlib import Path
from .ea_inverse import paths, read_rows
from .evaluation_export import inline_json


def translations(project):
    return json.loads((project/'viewer/dataset/ea-inverse-ko.json').read_text())


def build_package(project, run, name):
    summary, result, _, _ = paths(project, run, name)
    sha = summary['files'][str(result.relative_to(project))]['sha256']
    ko = translations(project)
    if ko['snapshot_sha256'] != sha:
        raise ValueError('EA_TRANSLATION_SNAPSHOT_MISMATCH')
    dataset_path = project/'data/final'/run/'dataset.jsonl'
    if dataset_path.is_symlink() or hashlib.sha256(dataset_path.read_bytes()).hexdigest() != summary['input_sha256']:
        raise ValueError('ER_DISPLAY_DATASET_HASH_MISMATCH')
    ds_stat = dataset_path.stat()
    originals = {r['id']: r for r in read_rows(str(dataset_path), ds_stat.st_mtime_ns, ds_stat.st_size)}
    stat = result.stat()
    rows = read_rows(str(result), stat.st_mtime_ns, stat.st_size)
    expected = [f'id-{i:04d}' for i in range(1, 1355)]
    if [row['id'] for row in rows] != expected:
        raise ValueError('EA_ANNOTATOR_ID_COVERAGE')
    cases = []
    for row in rows:
        case = originals[row['id']]
        variants = {v['type']: v for v in row['variants']}
        if set(variants) != {'EA_01', 'EA_02'}:
            raise ValueError('EA_ANNOTATOR_TYPE_COVERAGE')
        items = []
        for kind in ('EA_01', 'EA_02'):
            v = variants[kind]
            actual = next(x for x in case['variants'] if x['type'] == kind)
            if any(actual[k] != v[k] for k in ('question', 'context', 'content_sha256')):
                raise ValueError('ER_DISPLAY_QC_MISMATCH')
            plan_path = project/v['source']['baseline_source']['variant_root']/'01-perturbation/03-result.json'
            if not plan_path.resolve().is_relative_to((project/'reports/run').resolve()) or plan_path.is_symlink():
                raise ValueError('ER_DISPLAY_PLAN_PATH')
            plan = json.loads(plan_path.read_text())['plan']
            targets = [n for n in plan['original_graph']['nodes'] if n.get('fact_id') == plan['target']]
            if not targets:
                raise ValueError('ER_DISPLAY_NO_REMOVAL_TARGET')
            removals = []
            for target in targets:
                start, end = target['span']
                if case['original']['context'][start:end] != target['text']:
                    raise ValueError('ER_DISPLAY_REMOVAL_SPAN_MISMATCH')
                removals.append({'start': start, 'end': end, 'text': target['text'],
                                 'label': target['fact_id'], 'unit': target.get('unit', '')})
            review = v['review_record']['inverse_review']
            if v['status'] != 'COMPLETED' or type(review['inverse_possible']) is not bool:
                raise ValueError('EA_ANNOTATOR_INCOMPLETE_REVIEW')
            evidence = []
            for e in review['evidence']:
                if v[e['field']][e['start']:e['end']] != e['quote']:
                    raise ValueError('EA_ANNOTATOR_EVIDENCE_MISMATCH')
                evidence.append({k: e[k] for k in ('field', 'start', 'end')})
            items.append({'type': kind, 'question': v['question'], 'context': v['context'],
                          'content_sha256': v['content_sha256'],
                          'removals': removals,
                          'removal_source': {'path': str(plan_path.relative_to(project)),
                                             'sha256': hashlib.sha256(plan_path.read_bytes()).hexdigest()},
                          'inverse_review': {**review, 'evidence': evidence},
                          'display_ko': {'missing_quantity': ko['missing_quantity'][review['missing_quantity']],
                                         'reason': ko['reason'][review['reason']]}})
        cases.append({'id': row['id'], 'source_dataset': row['source_dataset'],
                      'original_context': case['original']['context'], 'items': items})
    return {'format': 'finarch-ea-inverse-package-v1', 'run': run, 'snapshot_file': name,
            'snapshot_sha256': sha, 'package_id': sha, 'n': len(cases), 'items': 2*len(cases),
            'display_source_sha256': summary['input_sha256'], 'display_revision': 2,
            'taxonomy': {'EA_01': {'label': 'ER-1', 'name': 'Evidence Removal', 'description_ko': '첫 번째 입력의 근거를 원본에서 제거'},
                         'EA_02': {'label': 'ER-2', 'name': 'Evidence Removal', 'description_ko': '다른 입력의 근거를 원본에서 독립적으로 제거'}},
            'translation_version': ko['version'], 'cases': cases}


def render(project, run, name):
    package = build_package(project, run, name)
    folder = project/'viewer/dataset'
    html = (folder/'ea-inverse-annotator.html').read_text()
    for marker, filename in (('__STYLE__', 'ea-inverse-annotator.css'),
                             ('__STATE__', 'ea-inverse-annotation-state.js'),
                             ('__UI__', 'ea-inverse-annotator.js')):
        html = html.replace(marker, (folder/filename).read_text())
    return html.replace('__PACKAGE__', inline_json(package)).encode('utf-8')
