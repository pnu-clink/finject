"""Item-aligned nominal agreement; missing ratings never become judgments."""
from collections import Counter, defaultdict
import hashlib
import json

from .normalize import DECISIONS, TYPES


def kappa(matrix, total):
    n = len(matrix[0]) if matrix else 0
    result = {'method': 'Cohen' if n == 2 else 'Fleiss' if n > 2 else None,
              'kappa': None, 'agreement': None, 'unanimous': None,
              'included': len(matrix), 'excluded': total - len(matrix), 'total': total,
              'raters': n, 'observed': None, 'expected': None, 'reason': None}
    if n < 2:
        result['reason'] = '평가자 2명 이상의 공통 저장 판정이 필요합니다.'; return result
    if any(len(row) != n or any(value not in DECISIONS for value in row) for row in matrix):
        raise ValueError('Kappa requires complete rows with the same number of raters.')
    cases = len(matrix)
    observed = sum(sum(count * (count - 1) for count in Counter(row).values()) / (n * (n - 1)) for row in matrix) / cases
    if n == 2:
        left = Counter(row[0] for row in matrix); right = Counter(row[1] for row in matrix)
        expected = sum(left[d] * right[d] for d in DECISIONS) / cases ** 2
    else:
        counts = Counter(value for row in matrix for value in row)
        expected = sum((counts[d] / (cases * n)) ** 2 for d in DECISIONS)
    result.update(observed=observed, expected=expected, agreement=observed,
                  unanimous=sum(len(set(row)) == 1 for row in matrix) / cases)
    if abs(1 - expected) < 1e-12:
        result['reason'] = '모든 공통 판정이 한 범주여서 κ를 계산할 수 없습니다.'
    else: result['kappa'] = (observed - expected) / (1 - expected)
    return result


def document_scope(document):
    if document.get('comparison_scope'):
        return tuple(document['comparison_scope'])
    return (document['source_format'], document.get('run'), document.get('round'), document.get('package_id'))


def align_scopes(documents):
    """Join explicit legacy run metadata to one unambiguous native package."""
    native = [doc for doc in documents if doc.get('source_format') == 'finarch-evaluation-results-v1'
              and doc.get('evaluations') is not None and all(doc.get(key) for key in ('run', 'round', 'package_id'))]
    output = []
    for doc in documents:
        if doc.get('source_format') != 'finject-labels' or not isinstance(doc.get('run'), str) or not doc['run']:
            output.append(doc); continue
        records = {(row.get('case'), row.get('variant')) for row in doc.get('evaluations') or []}
        candidates = {document_scope(other) for other in native
                      if other['run'] == doc['run']
                      and all(not doc.get(key) or doc[key] == other[key] for key in ('round', 'package_id'))
                      and records and records.issubset({(row.get('case'), row.get('variant')) for row in other['evaluations']})}
        if len(candidates) == 1:
            output.append({**doc, 'comparison_scope': next(iter(candidates)),
                           'scope_binding': 'EXPLICIT_RUN_AND_UNIQUE_PACKAGE'})
        else:
            output.append(doc)
    return output


def dataset_label(group):
    hints = [str(value).lower().replace('-', '').replace('_', '') for value in group.get('dataset_hints', [])]
    if any('tatqa' in value for value in hints) or (group.get('run') and
            {value['value'] for value in group.get('source_types', [])} == {'TAT-QA'}):
        return 'TAT-QA'
    # FinanceReasoning is the owner's comparison family; source_types keeps the actual provenance.
    return 'FinanceReasoning 합본' if group.get('run') else 'FinanceReasoning'


def group_id(scope):
    return hashlib.sha256(json.dumps(scope, ensure_ascii=False).encode()).hexdigest()[:16]


def comparable_record(record):
    return {key: record.get(key) for key in ('decision', 'confirmed', 'comment', 'inserted', 'removed', 'issues')}


def build_view(documents):
    groups = defaultdict(list)
    for document in align_scopes(documents):
        if document.get('evaluations') is not None: groups[document_scope(document)].append(document)
    output = []
    for scope, files in groups.items():
        reviewers = list(dict.fromkeys(document['reviewer'] or '이름 없음 · ' + document['filename'] for document in files))
        by_case = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        for document in files:
            reviewer = document['reviewer'] or '이름 없음 · ' + document['filename']
            header_errors = [issue['code'] for issue in document['issues'] if issue['source_index'] is None]
            for record in document['evaluations']:
                if not isinstance(record.get('case'), str) or not isinstance(record.get('variant'), str): continue
                by_case[record['case']][record['variant']][reviewer].append({**record,
                    'issues': list(dict.fromkeys(record['issues'] + header_errors)), 'file_id': document['id']})
        cases = []; matrices = defaultdict(list); total_types = Counter(); flag_totals = Counter()
        for case_name in sorted(by_case, key=lambda name: (int(name.split('-')[-1]) if name.split('-')[-1].isdigit() else 10**10, name)):
            rows = []
            for variant, label, title in TYPES:
                cells = {}; flags = []; content = []; valid = []
                available = bool(by_case[case_name].get(variant))
                if available: total_types[variant] += 1
                for reviewer in reviewers:
                    records = by_case[case_name][variant].get(reviewer, [])
                    if not records:
                        cells[reviewer] = {'decision': None, 'confirmed': False, 'comment': '', 'issues': [], 'missing': True}
                        continue
                    first = records[0]; signatures = {json.dumps(comparable_record(record), sort_keys=True, ensure_ascii=False) for record in records}
                    errors = list(dict.fromkeys(error for record in records for error in record['issues']))
                    if len(signatures) > 1: errors.append('CONFLICTING_REVIEWER_FILES')
                    cell = {key: first.get(key) for key in ('decision', 'confirmed', 'comment', 'updated_at', 'source_index')}
                    cell.update(issues=errors, file_ids=list(dict.fromkeys(record['file_id'] for record in records)),
                                missing=not first['confirmed'] or not first['decision'])
                    if len(signatures) > 1:
                        cell['alternatives'] = [{**comparable_record(record), 'file_id': record['file_id']} for record in records]
                    cells[reviewer] = cell
                    if 'inserted' in first or 'removed' in first:
                        content.append({'reviewer': reviewer, 'inserted': first.get('inserted', ''), 'removed': first.get('removed', '')})
                    if first['confirmed'] and first['decision'] and not errors: valid.append(first['decision'])
                if any(cell['issues'] for cell in cells.values()): flags.append('FORMAT')
                signatures = {(entry['inserted'], entry['removed']) for entry in content}
                if len(signatures) > 1: flags.append('CONTENT')
                if len(set(valid)) > 1: flags.append('DISAGREE')
                if any(cell['decision'] == 'REJECTED' for cell in cells.values()): flags.append('REJECTED')
                if any(cell['decision'] == 'PENDING' for cell in cells.values()): flags.append('PENDING')
                if any(cell['missing'] for cell in cells.values()): flags.append('MISSING')
                if any(cell['comment'].strip() for cell in cells.values()): flags.append('NOTE')
                eligible = available and len(reviewers) >= 2 and len(valid) == len(reviewers) and 'CONTENT' not in flags
                if eligible: matrices[variant].append([cells[reviewer]['decision'] for reviewer in reviewers])
                for flag in flags: flag_totals[flag] += 1
                rows.append({'variant': variant, 'label': label, 'title': title, 'cells': cells,
                             'content': content[:1] if len(signatures) <= 1 else content,
                             'flags': flags, 'eligible': eligible, 'available': available})
            case_flags = list(dict.fromkeys(flag for row in rows for flag in row['flags']))
            cases.append({'case': case_name, 'rows': rows, 'flags': case_flags})
        metrics = []
        for variant, _, title in TYPES:
            metric = kappa(matrices[variant], total_types[variant])
            metric.update(variant=variant, title=title, raters=len(reviewers),
                          method='Cohen' if len(reviewers) == 2 else 'Fleiss' if len(reviewers) > 2 else None)
            metrics.append(metric)
        output.append({'id': group_id(scope), 'source_format': scope[0], 'run': scope[1], 'round': scope[2],
                       'dataset_hints': list(dict.fromkeys(file['dataset'] for file in files if isinstance(file.get('dataset'), str))),
                       'package_id': scope[3], 'reviewers': reviewers, 'file_ids': [file['id'] for file in files],
                       'cases': cases, 'metrics': metrics, 'totals': dict(flag_totals),
                       'flagged_entries': sum(any(flag in row['flags'] for flag in ('REJECTED', 'PENDING')) for case in cases for row in case['rows']),
                       'disagreement_cases': sum('DISAGREE' in case['flags'] for case in cases)})
    return output
