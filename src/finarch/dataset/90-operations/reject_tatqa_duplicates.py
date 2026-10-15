"""Audit original CodeTAT-QA questions and record owner-directed TAT-QA exclusions."""
import argparse
from collections import defaultdict
from decimal import Decimal, InvalidOperation
import hashlib
from importlib import import_module
import json
from pathlib import Path
import re
from datetime import datetime, timezone

gate = import_module('finarch.dataset.90-operations.preparation_gate')
policy = import_module('finarch.dataset.03-release.export_policy')

# These three differences preserve the requested quantity, years and operation.
# Other wording differences are deliberately not treated as equivalence.
EQUIVALENT = {
    'what is the total network equipment between 2018 to 2019?':
        'what is the total network equiption between 2018 to 2019?',
    'what was the change in the total number of shares purchased between the second to third month period (in thousands)?':
        'what was the change in the total number of shares purchased between the second to third month period?',
    'what is the average proportion of cost of revenue as a percentage of revenue in 2017 and 2018?':
        'what is the average proportion of cost of revenue as a percentage of the total revenue in 2017 and 2018?',
}


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def question(text):
    text = re.sub(r'\s+Answer (?:to|as)\b.*$', '', text, flags=re.I)
    return ' '.join(text.replace('’', "'").casefold().split())


def cell(value):
    text = ' '.join(str(value).split())
    number = text.replace(',', '').replace('%', '').strip('$€£` ').replace('−', '-')
    if number.startswith('(') and number.endswith(')'):
        number = '-' + number[1:-1].strip()
    try:
        return 'N:' + str(Decimal(number).normalize())
    except InvalidOperation:
        return 'T:' + re.sub(r'[^a-z0-9]', '', text.casefold())


def rows(sample):
    return [row for table in sample['source_content']['tables'] for row in table['rows']
            if row and str(row[0]).strip() and any(cell(v).startswith('N:') for v in row[1:])]


def subsequence(values, other):
    remaining = iter(other)
    return all(any(value == candidate for candidate in remaining) for value in values)


def table_evidence(code, tat):
    found = []
    for row in rows(code):
        values = [cell(v) for v in row[1:] if str(v).strip()]
        for candidate in rows(tat):
            if cell(row[0]) == cell(candidate[0]) and subsequence(
                    values, [cell(v) for v in candidate[1:] if str(v).strip()]):
                found.append({'codetat_row': row, 'tatqa_row': candidate})
                break
    return found


def eligible(run, case, report_rows):
    parent = run / '01-preparation' / case
    state = read(parent / 'run.json')
    recorded, _ = policy.review(gate.active_case_path(parent), 'preparation')
    if state.get('status') != 'PASS' or policy.current_decision(state, recorded) in policy.REJECTED:
        return False
    results = report_rows.get(case, [])
    if len(results) != 7:
        return False
    for result in results:
        folder = run / result['origin']
        state = read(folder / 'run.json')
        recorded, _ = policy.review(folder, 'generation')
        if state.get('status') != 'PASS' or policy.current_decision(state, recorded) in policy.REJECTED:
            return False
    return True


def audit(run, code_path, tat_path, raw_path):
    code, tat = read(code_path), read(tat_path)
    selection = read(run / 'input-selection.json')
    if Path(selection['input_path']).resolve() != tat_path.resolve():
        raise ValueError('TARGET_INPUT_MISMATCH')
    if set(selection['cases']) != {r['id'] for r in tat}:
        raise ValueError('TARGET_CASES_MISMATCH')
    raw_questions = {}
    for doc in read(raw_path):
        for item in doc['questions']:
            raw_questions['tatqa-' + item['uid']] = (doc, item)
    index = defaultdict(list)
    for item in tat:
        doc, raw = raw_questions[item['raw_id']]
        if (item['question'] != raw['question'] or item['provenance']['document_id'] != doc['table']['uid']
                or item['source_content']['tables'][0]['rows'] != doc['table']['table']
                or item['provenance']['sha256'] != sha(raw_path)):
            raise ValueError('TATQA_PROVENANCE_MISMATCH:' + item['id'])
        index[question(item['question'])].append(item)
    upstream = {}
    source_files = {}
    for item in code:
        source = item['provenance']
        source_id = source['source_id']
        if not source_id.startswith('CodeTAT-QA-'):
            raise ValueError('NOT_CODETAT_QA')
        if source['name'] not in source_files:
            path = raw_path.parent / (source['name'] + '.json')
            if sha(path) != source['sha256']:
                raise ValueError('FINANCE_SOURCE_HASH_MISMATCH')
            source_files[source['name']] = {'path': str(path.resolve()), 'sha256': sha(path)}
            for row in read(path):
                if row['source'].startswith('CodeTAT-QA-'):
                    upstream[row['source']] = row
        original = upstream[source_id]
        if original['question'] != item['question']:
            raise ValueError('CODETAT_QUESTION_PROVENANCE_MISMATCH')
    matches, unmatched = [], []
    for item in code:
        original_q = question(item['question'])
        target_q = EQUIVALENT.get(original_q, original_q)
        candidates = index.get(target_q, [])
        ranked = sorted([(len(table_evidence(item, other)), other['id'], other)
                         for other in candidates], reverse=True, key=lambda value: value[:2])
        if not ranked or ranked[0][0] < 2 or (len(ranked) > 1 and ranked[0][0] == ranked[1][0]):
            unmatched.append({'codetat_case': item['id'], 'source_id': item['provenance']['source_id'],
                              'question': item['question'], 'reason': 'NO_CONFIRMED_SAME_QUESTION_AND_TABLE',
                              'candidates': [{'tatqa_case': cid, 'matched_table_rows': score}
                                             for score, cid, _ in ranked]})
            continue
        _, _, other = ranked[0]
        matches.append({'tatqa_case': other['id'], 'tatqa_raw_id': other['raw_id'],
                        'tatqa_document_id': other['provenance']['document_id'],
                        'codetat_case': item['id'], 'codetat_source_id': item['provenance']['source_id'],
                        'codetat_source': item['provenance'], 'codetat_question': item['question'],
                        'tatqa_question': other['question'],
                        'question_match': 'REVIEWED_EQUIVALENT_WORDING' if original_q != target_q else 'NORMALIZED_EXACT',
                        'table_evidence': table_evidence(item, other),
                        'original_finance_record_sha256': hashlib.sha256(json.dumps(
                            upstream[item['provenance']['source_id']], sort_keys=True).encode()).hexdigest()})
    ids = sorted({item['tatqa_case'] for item in matches})
    reports = defaultdict(list)
    for row in read(run / '02-generation/result-report.json')['rows']:
        reports[row['case']].append(row)
    before = [case for case in selection['cases'] if eligible(run, case, reports)]
    return {'generated_at': datetime.now(timezone.utc).isoformat(), 'target_run': run.name,
            'comparison_scope': 'ALL_CODETAT_QA_INPUTS_REGARDLESS_OF_AUTOMATIC_STATUS',
            'codetat_count': len(code), 'tatqa_count': len(tat), 'matches': matches,
            'rejected_cases': ids, 'unmatched_codetat_questions': unmatched,
            'eligible_before': before, 'eligible_after_expected': [cid for cid in before if cid not in ids],
            'sources': [{'path': str(path.resolve()), 'sha256': sha(path)}
                        for path in (code_path, tat_path, raw_path)] + list(source_files.values()),
            'automatic_results_preserved': True, 'model_calls': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--codetat-input', type=Path, required=True)
    parser.add_argument('--tatqa-input', type=Path, required=True)
    parser.add_argument('--raw-tatqa', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    run = args.run.resolve()
    if read(run / 'sequence-status.json').get('status') != 'COMPLETED':
        raise ValueError('TARGET_RUN_MUST_BE_COMPLETED')
    report = audit(run, args.codetat_input, args.tatqa_input, args.raw_tatqa)
    output = run / 'deduplication/codetatqa'
    output.mkdir(parents=True, exist_ok=True)
    if not args.apply:
        gate.write(output / 'plan.json', report)
    else:
        plan = read(output / 'plan.json')
        if any(plan[key] != report[key] for key in ('sources', 'matches', 'rejected_cases', 'eligible_before')):
            raise ValueError('AUDITED_PLAN_CHANGED')
        gate.write(output / 'prior-decisions.json', {cid: policy.review(
            gate.active_case_path(run / '01-preparation' / cid), 'preparation')[0]
            for cid in report['rejected_cases']})
        markers = {str(path.relative_to(run)): sha(path) for path in
                   [*(run / '01-preparation').glob('test-*/run.json'),
                    *(run / '02-generation').glob('*-round/test-*/*/run.json')]}
        grouped = defaultdict(list)
        for match in report['matches']:
            grouped[match['tatqa_case']].append(match)
        for cid, records in grouped.items():
            sources = ', '.join(r['codetat_source_id'] + ' (FinanceReasoning ' + r['codetat_case'] + ')'
                                for r in records)
            reason = ('Owner-directed duplicate exclusion: this original TAT-QA question and table '
                      'match ' + sources + '. Evidence: deduplication/codetatqa/plan.json. '
                      'Exclude the entire question including all seven generated types; '
                      'automatic validation results remain unchanged.')
            gate.record_decision(run / '01-preparation' / cid, 'REJECTED',
                                 'owner-directed-source-deduplication', reason)
            with (output / 'events.jsonl').open('a') as stream:
                stream.write(json.dumps({'case': cid, 'decision': 'REJECTED',
                                         'source_ids': [r['codetat_source_id'] for r in records]}) + '\n')
        if any(sha(run / path) != digest for path, digest in markers.items()):
            raise ValueError('AUTOMATIC_STATE_CHANGED')
        for source in report['sources']:
            if sha(source['path']) != source['sha256']:
                raise ValueError('ORIGINAL_SOURCE_CHANGED')
        verification = audit(run, args.codetat_input, args.tatqa_input, args.raw_tatqa)
        if verification['eligible_before'] != report['eligible_after_expected']:
            raise ValueError('ELIGIBLE_CASES_MISMATCH')
        report['eligible_after'] = verification['eligible_before']
        report['status'] = 'APPLIED_AND_VERIFIED'
        gate.write(output / 'result.json', report)
    print(json.dumps({'mode': 'APPLY' if args.apply else 'AUDIT', 'codetat': report['codetat_count'],
                      'tatqa': report['tatqa_count'], 'confirmed_duplicates': len(report['rejected_cases']),
                      'not_confirmed': len(report['unmatched_codetat_questions']),
                      'eligible_before': len(report['eligible_before']),
                      'eligible_after': len(report.get('eligible_after', report['eligible_after_expected']))}))


if __name__ == '__main__':
    main()
