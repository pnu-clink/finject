"""Observe two independent collections with identical provider request bodies."""
import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = __import__('finarch.experiments.02-analysis.legacy.content-analysis.stability_review', fromlist=['ROOT']).ROOT
read_rows = __import__('finarch.experiments.02-analysis.legacy.content-analysis.stability_review', fromlist=['read_rows']).read_rows
sha = __import__('finarch.experiments.02-analysis.legacy.content-analysis.stability_review', fromlist=['sha']).sha
table = __import__('finarch.experiments.02-analysis.legacy.content-analysis.stability_review', fromlist=['table']).table


def signature(row):
    """RR01: Distinguish missing responses, explicit null, and signed scaled values."""
    response = row.get('response')
    if not isinstance(response, dict) or 'answer' not in response:
        return None
    value = response['answer']
    if value is None:
        return ('NULL',)
    if type(value) not in (int, float):
        return None
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        return None
    if not number.is_finite():
        return None
    coefficient = '0' if number == 0 else str(number.normalize())
    return ('NUMERIC', coefficient, response.get('answer_meta', {}).get('scale'))


def compare(left, right, same_payload, same_model):
    """RR02: Compare observed answers only when request and model labels match."""
    a, b = signature(left), signature(right)
    eligible = same_payload and same_model
    observed = eligible and a is not None and b is not None
    both_numeric = observed and a[0] == b[0] == 'NUMERIC'
    pair = {k: left[k] for k in ('case', 'variant', 'prompt_condition', 'reasoning')}
    pair.update(left_trial_id=left['trial_id'], right_trial_id=right['trial_id'],
                same_provider_payload=same_payload, same_reported_model_label=same_model,
                eligible=eligible, answers_observed=observed,
                left_signature=a, right_signature=b,
                same_presence=(a[0] == b[0]) if observed else None,
                same_answer_and_scale=(a == b) if observed else None,
                both_numeric=both_numeric,
                same_numeric_and_scale=(a == b) if both_numeric else None,
                left_valid=left['saved_status'] == 'VALID', right_valid=right['saved_status'] == 'VALID',
                same_evidence=(left['response'].get('evidence') == right['response'].get('evidence')) if observed else None,
                left_original_outcome=left['original_outcome'], right_original_outcome=right['original_outcome'],
                left_result_path=left['result_path'], right_result_path=right['result_path'])
    return pair


def summarize(pairs):
    observed = [p for p in pairs if p['answers_observed']]
    numeric = [p for p in observed if p['both_numeric']]
    eligible = [p for p in pairs if p['eligible']]
    return {'planned_pairs': len(pairs), 'eligible_pairs': len(eligible),
            'answer_observed_pairs': len(observed), 'answer_unassessed_pairs': len(pairs)-len(observed),
            'same_presence': sum(p['same_presence'] is True for p in observed),
            'same_answer_and_scale': sum(p['same_answer_and_scale'] is True for p in observed),
            'changed_answer_or_scale': sum(p['same_answer_and_scale'] is False for p in observed),
            'numeric_to_null': sum(p['left_signature'][0] == 'NUMERIC' and p['right_signature'][0] == 'NULL' for p in observed),
            'null_to_numeric': sum(p['left_signature'][0] == 'NULL' and p['right_signature'][0] == 'NUMERIC' for p in observed),
            'both_numeric_pairs': len(numeric), 'same_numeric_and_scale': sum(p['same_numeric_and_scale'] for p in numeric),
            'same_evidence_array': sum(p['same_evidence'] is True for p in observed),
            'both_valid': sum(p['left_valid'] and p['right_valid'] for p in eligible),
            'valid_to_invalid': sum(p['left_valid'] and not p['right_valid'] for p in eligible),
            'invalid_to_valid': sum(not p['left_valid'] and p['right_valid'] for p in eligible),
            'stable_original_numeric_mismatch': sum(p['variant'] == 'ORIGINAL' and p['same_answer_and_scale'] is True
                and p['left_original_outcome'] == p['right_original_outcome'] == 'NUMERIC_MISMATCH' for p in observed)}


def build(first, second, output):
    """RR03–05: Verify saved payloads, preserve sources, and write paired evidence."""
    first, second, output = Path(first).resolve(), Path(second).resolve(), Path(output).resolve()
    if output in (first, second) or first in output.parents or second in output.parents:
        raise ValueError('OUTPUT_MUST_NOT_REPLACE_INPUT_ANALYSIS')
    key = lambda row: tuple(row[k] for k in ('case', 'variant', 'prompt_condition', 'reasoning'))
    datasets = [read_rows(folder/'rows.jsonl') for folder in (first, second)]
    maps = [{key(row): row for row in data} for data in datasets]
    if any(len(data) != len(mapping) for data, mapping in zip(datasets, maps)) or set(maps[0]) != set(maps[1]):
        raise ValueError('EXACT_UNIQUE_CONDITION_COVERAGE_REQUIRED')
    hashes = {str((folder/'rows.jsonl').relative_to(ROOT)): sha(folder/'rows.jsonl') for folder in (first, second)}
    pairs, model_labels = [], Counter()
    for condition in sorted(maps[0]):
        left, right = maps[0][condition], maps[1][condition]
        bodies, models = [], []
        for row in (left, right):
            if not row.get('result_path'):
                bodies.append(None); models.append(None); continue
            result_file = ROOT/row['result_path']
            body_file = result_file.with_name('provider-request-wire.json')
            if not body_file.is_file():
                bodies.append(None); models.append(None); continue
            for path in (result_file, body_file):
                hashes[str(path.relative_to(ROOT))] = sha(path)
            result = json.loads(result_file.read_text())
            bodies.append(body_file.read_bytes())
            models.append(result.get('model_version'))
            model_labels[str(result.get('model_version'))] += 1
        same_body = all(isinstance(body, bytes) for body in bodies) and bodies[0] == bodies[1]
        same_model = all(isinstance(model, str) and model for model in models) and models[0] == models[1]
        pairs.append(compare(left, right, same_body, same_model))
    groups, conditions, cases = defaultdict(list), defaultdict(list), defaultdict(list)
    for pair in pairs:
        groups[(pair['variant'], pair['prompt_condition'], pair['reasoning'])].append(pair)
        scope = 'ORIGINAL' if pair['variant'] == 'ORIGINAL' else 'VARIANTS'
        conditions[(scope, pair['prompt_condition'], pair['reasoning'])].append(pair)
        cases[pair['case']].append(pair)
    report = {'kind': 'TWO_COLLECTION_IDENTICAL_REQUEST_OBSERVATIONS', 'created_at': datetime.now(timezone.utc).isoformat(),
              'first_run': datasets[0][0]['run_id'], 'second_run': datasets[1][0]['run_id'],
              'independent_originals': len({p['case'] for p in pairs}), 'collections': 2,
              'overall': summarize(pairs), 'model_label_counts': dict(model_labels),
              'groups': [{**dict(zip(('variant','prompt_condition','reasoning'), group)), **summarize(items)}
                         for group, items in sorted(groups.items())],
              'by_scope_prompt_reasoning': [{**dict(zip(('scope','prompt_condition','reasoning'), group)), **summarize(items)}
                         for group, items in sorted(conditions.items())],
              'by_original_case': [{'case': case, **summarize(items),
                    'variant_p0': summarize([p for p in items if p['variant'] != 'ORIGINAL' and p['prompt_condition'] == 'P0']),
                    'variant_p1': summarize([p for p in items if p['variant'] != 'ORIGINAL' and p['prompt_condition'] == 'P1'])}
                    for case, items in sorted(cases.items())],
              'limitations': ['Two independent calls per condition, not a reliability estimate over many repetitions.',
                             'A matching provider model label does not identify immutable backend weights.',
                             'Signed numeric coefficient plus scale equality is not semantic correctness.',
                             'Variants and conditions share 100 original-case clusters.',
                             'Exact evidence-array equality is not equality of supporting meaning.'],
              'new_model_calls': 0, 'semantic_scoring': 'NOT_PERFORMED'}
    if not all(sha(ROOT/path) == digest for path, digest in hashes.items()):
        raise ValueError('SOURCE_CHANGED_DURING_REPEAT_ANALYSIS')
    output.mkdir(parents=True, exist_ok=True)
    (output/'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    (output/'pairs.jsonl').write_text(''.join(json.dumps(p,ensure_ascii=False)+'\n' for p in pairs))
    (output/'verification.json').write_text(json.dumps({'source_files':len(hashes),'source_sha256':hashes,
        'all_source_hashes_unchanged':True,'analyzer_sha256':sha(Path(__file__)),
        'viewer_verified':False,'user_review_completed':False,'new_model_calls':0},indent=2)+'\n')
    total = report['overall']
    lines = ['# Comparing the response to the same call twice', '',
        f"`{report['first_run']}` → `{report['second_run']}` · The original {report['independent_originals']}· plan {total['planned_pairs']:,}Couple of them.", '',
        'The same pair of model names that the actual provider requested JSON bytes and the model names returned by the provider were compared. The key sequence is also included in the transfer byte comparison. The same model name does not prove the same until the internal overweight revision. It is an observation of two collected results that did not reuse the response, and is read apart from the correct response rate.', '',
        table(['Observation','Double number.'],[(k,total[k]) for k in ('planned_pairs','eligible_pairs','answer_observed_pairs','answer_unassessed_pairs','same_presence','same_answer_and_scale','changed_answer_or_scale','numeric_to_null','null_to_numeric','both_numeric_pairs','same_numeric_and_scale','both_valid','valid_to_invalid','invalid_to_valid','stable_original_numeric_mismatch')]), '',
        'The same answer is if both the signed number and the scale are equal, or both are explicitly null. `stable_original_numeric_mismatch`And if both of them have the same number, but it\'s not consistent with the original reference number, then stability and accuracy are different properties.', '',
        table(['Scope','P','Inference','Plans are in place.','The observation pairs.','Number, unit, and bin are the same.','Values, levels and values change','Number → zero','null→ number'],
              [[g['scope'],g['prompt_condition'],g['reasoning'],g['planned_pairs'],g['answer_observed_pairs'],g['same_answer_and_scale'],g['changed_answer_or_scale'],g['numeric_to_null'],g['null_to_numeric']] for g in report['by_scope_prompt_reasoning']]), '',
        table(['Type','P','Inference','Plans are in place.','The observation pairs.','Number, unit, and bin are the same.','Values, levels and values change','Both numbers.','The value and unit are the same.'],
              [[g['variant'],g['prompt_condition'],g['reasoning'],g['planned_pairs'],g['answer_observed_pairs'],g['same_answer_and_scale'],g['changed_answer_or_scale'],g['both_numeric_pairs'],g['same_numeric_and_scale']] for g in report['groups']]), '',
        'Two observations do not confirm long-term trust or the repeated dispersal of the collection. 100The originals are a developmental group, and the variations and conditions of the same originals are not independent samples, and it\'s not an underestimate of whether the explanations are meaningful or correct.', '',
        '♪ A bunch of different elements ♪', '',
        'The observed value, unit or numerical value changes a lot. 10The original is shown after death. 100The denominator of the source is in the by_original_case of summary.json. The ranking is not the correct answer to the problem or the new meaning error score.', '',
        table(['Source text','Observation and planning','The total response changes.','Change of P0','Change of P1','Number → zero','null→ number'],
              [[g['case'],f"{g['answer_observed_pairs']}/{g['planned_pairs']}",g['changed_answer_or_scale'],
                f"{g['variant_p0']['changed_answer_or_scale']}/{g['variant_p0']['answer_observed_pairs']}",
                f"{g['variant_p1']['changed_answer_or_scale']}/{g['variant_p1']['answer_observed_pairs']}",g['numeric_to_null'],g['null_to_numeric']]
               for g in sorted(report['by_original_case'], key=lambda g:(-g['changed_answer_or_scale'],g['case']))[:10]]), '']
    (output/'analysis.md').write_text('\n'.join(lines))
    template = ROOT/'src/finarch/documentation/templates/experiment-repeat-analysis.md'
    text = template.read_text().replace('{{first_run}}', report['first_run']).replace('{{second_run}}',report['second_run'])
    (output/'README.md').write_text(text)
    with (output/'events.jsonl').open('a') as stream:
        stream.write(json.dumps({'at':report['created_at'],'event':'IDENTICAL_REQUEST_REPEAT_REVIEW_COMPLETED',
                                 'pairs':len(pairs),'new_model_calls':0})+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--first', required=True)
    parser.add_argument('--second', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = build(args.first, args.second, args.output)
    print(json.dumps(result['overall']))
