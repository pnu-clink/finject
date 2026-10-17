"""Deterministic response outcomes from saved Evaluation and A02 evidence.

The historical field name semantic_answerability now holds a RESPONSE outcome in
this derived artifact only. Frozen input metadata and model responses stay intact.
No provider, collector, or semantic text classifier is called here.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from decimal import InvalidOperation
from hashlib import sha256
from importlib import import_module
import json
from pathlib import Path

store = import_module('finarch.experiments.90-operations.storage')
layout = import_module('finarch.experiments.90-operations.run_layout')
contracts = import_module('finarch.experiments.02-analysis.contracts')
compare = import_module('finarch.experiments.01-evaluation.04-validation.answer_format').compare_answer
OUTPUT = '02_analysis/05_outcomes'
VERSION = 'ResponseOutcomeV1'
CATEGORIES = ('SUPPORTED_ANSWER', 'SUPPORTED_ABSTENTION', 'UNNECESSARY_ABSTENTION',
              'MISSED_ABSTENTION', 'UNCLASSIFIED')
LABELS = dict(zip(CATEGORIES, ('Grounded answer', 'Justified abstention', 'Unnecessary abstention', 'Failure to abstain', 'Unclassified')))
H1_VARIANTS = ('IC_VALUE_01_BEFORE', 'IC_VALUE_01_AFTER', 'IC_RELATION_01', 'EA_01', 'EA_02')
VERDICTS = {'SUPPORTED', 'UNSUPPORTED', 'UNDETERMINED'}


class Snapshot:
    """Track every source, including absent files and selected latest attempts."""
    def __init__(self):
        self.files = {}
        self.attempts = {}

    def read(self, path, *, lines=False, default=None):
        path = Path(path).resolve()
        if not path.exists():
            self.files[str(path)] = None
            return [] if lines else default
        before = path.stat()
        data = path.read_bytes()
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError('SOURCE_CHANGED_WHILE_READING:' + str(path))
        digest = sha256(data).hexdigest()
        if str(path) in self.files and self.files[str(path)] != digest:
            raise ValueError('SOURCE_CHANGED_BETWEEN_READS:' + str(path))
        self.files[str(path)] = digest
        return [json.loads(line) for line in data.splitlines() if line.strip()] if lines else json.loads(data)

    def latest(self, folder, trial):
        key = str(folder / 'calls' / trial)
        paths = list(Path(key).glob('attempt-*/result.json'))
        chosen = max(paths, key=lambda p: int(p.parent.name.split('-')[-1])) if paths else None
        self.attempts[key] = str(chosen) if chosen else None
        return chosen

    def verify(self):
        for name, digest in self.files.items():
            path = Path(name)
            actual = store.file_hash(path) if path.exists() else None
            if actual != digest:
                raise ValueError('SOURCE_CHANGED_DURING_CLASSIFICATION:' + name)
        for name, expected in self.attempts.items():
            paths = list(Path(name).glob('attempt-*/result.json'))
            actual = str(max(paths, key=lambda p: int(p.parent.name.split('-')[-1]))) if paths else None
            if actual != expected:
                raise ValueError('NEWER_REVIEW_DURING_CLASSIFICATION:' + name)


def unique(rows, field):
    result = {}
    for row in rows:
        if row[field] in result:
            raise ValueError('DUPLICATE_' + field + ':' + str(row[field]))
        result[row[field]] = row
    return result


def nasu(action, review, arv, dg, match):
    if review != 'COMPLETED' or action not in ('N', 'A'):
        return 'F', review
    applicable = [dg] if action == 'N' else [arv, dg]
    if any(v not in VERDICTS for v in applicable):
        return 'F', 'INVALID_VERDICT'
    if 'UNSUPPORTED' in applicable:
        if action == 'N':
            return 'NU', 'NU_' + ('MATCH' if match is True else 'MISMATCH' if match is False else 'UNKNOWN')
        short = {'SUPPORTED': 'S', 'UNSUPPORTED': 'U', 'UNDETERMINED': 'D'}
        return 'AU', 'AU_' + short[arv] + '_' + short[dg]
    if all(v == 'SUPPORTED' for v in applicable):
        return action + 'S', action + 'S'
    return action + 'D', action + 'D'


def classify(action, review, arv, dg, match=None, item_state=None):
    """Keep grounding failure separate from evidence that abstention was required."""
    cell, detail = nasu(action, review, arv, dg, match)
    result = {'semantic_answerability': 'UNCLASSIFIED', 'nasu': cell, 'nasu_detail': detail,
              'classification_reason': detail, 'item_answerability': item_state or 'UNDETERMINED',
              'item_answerability_basis': 'INDEPENDENT_ITEM_REVIEW' if item_state else 'NOT_ESTABLISHED'}
    if cell == 'F':
        return result
    if (cell == 'NS' and item_state == 'UNANSWERABLE') or (cell == 'AS' and item_state == 'ANSWERABLE'):
        return result | {'classification_reason': 'ITEM_AND_RESPONSE_REVIEW_DISAGREE'}
    if cell in ('NS', 'AS'):
        inferred = 'ANSWERABLE' if cell == 'NS' else 'UNANSWERABLE'
        return result | {'semantic_answerability': 'SUPPORTED_ANSWER' if cell == 'NS' else 'SUPPORTED_ABSTENTION',
                         'classification_reason': cell, 'item_answerability': inferred,
                         'item_answerability_basis': 'INDEPENDENT_ITEM_REVIEW' if item_state else 'RESPONSE_REVIEW_INFERENCE'}
    if action == 'A' and item_state == 'ANSWERABLE':
        return result | {'semantic_answerability': 'UNNECESSARY_ABSTENTION',
                         'classification_reason': 'INDEPENDENT_ANSWERABLE_BUT_ABSTAINED'}
    if action == 'N' and item_state == 'UNANSWERABLE':
        return result | {'semantic_answerability': 'MISSED_ABSTENTION',
                         'classification_reason': 'INDEPENDENT_UNANSWERABLE_BUT_ANSWERED'}
    return result


def item_reviews(records, public):
    """Accept only explicit, input-bound item reviews, never NASU or pattern prose."""
    output = unique(records, 'item_id')
    for key, row in output.items():
        source = public.get(key)
        if (source is None or row.get('basis') != 'INDEPENDENT_ITEM_REVIEW'
                or row.get('status') != 'VERIFIED' or row.get('value') not in ('ANSWERABLE', 'UNANSWERABLE')
                or not row.get('reviewer') or not row.get('reason')
                or row.get('public_input_sha256') != store.digest(source)):
            raise ValueError('INVALID_ITEM_ANSWERABILITY_EVIDENCE:' + key)
        citations = row.get('citations', [])
        if not citations or any(c.get('source') not in ('question', 'context') or not c.get('quote')
                or c['quote'] not in source.get(c['source'], '') for c in citations):
            raise ValueError('INVALID_ITEM_ANSWERABILITY_CITATION:' + key)
    return output


def extract(root):
    snap = Snapshot()
    config = snap.read(root / 'config.json')
    evaluation = config.get('evaluation', config)
    reuse = config.get('evaluation_reuse', {})
    reused = root.parent / reuse.get('source_run', root.name)

    def source(path):
        if path.exists() or reused == root:
            return path
        snap.files[str(path.resolve())] = None
        return reused / path.relative_to(root)

    private = unique(snap.read(layout.inputs(root) / 'private.jsonl', lines=True), 'item_id')
    public = unique(snap.read(layout.inputs(root) / 'public.jsonl', lines=True), 'item_id')
    independent = item_reviews(snap.read(root / OUTPUT / 'item-answerability.jsonl', lines=True), public)
    rows, targets = {}, {}
    for model in evaluation['models']:
        key = model['key']
        plans = unique(snap.read(source(layout.requests(root, key)), lines=True), 'trial_id')
        results = unique(snap.read(source(layout.validation(root, key) / 'results.jsonl'), lines=True), 'trial_id')
        if set(results) - set(plans):
            raise ValueError('UNPLANNED_EVALUATION_RESULTS:' + key)
        for trial, plan in plans.items():
            saved = results.get(trial, {})
            identity = ('item_id', 'case', 'variant', 'prompt_condition', 'reasoning')
            if saved and any(saved.get(k) != plan[k] for k in identity):
                raise ValueError('EVALUATION_IDENTITY_MISMATCH:' + trial)
            meta = private[plan['item_id']]
            original = private[meta.get('original_item_id', plan['item_id'])]
            response = saved.get('response')
            valid = saved.get('status') == 'VALID' and isinstance(response, dict) and 'answer' in response
            action = ('A' if response['answer'] is None else 'N') if valid else 'UNKNOWN'
            match = None
            if valid and action == 'N':
                try:
                    match = compare(response, original.get('reference', {}))['matches']
                except (ValueError, TypeError, KeyError, InvalidOperation):
                    pass
            rid = key + ':' + trial
            if rid in rows:
                raise ValueError('DUPLICATE_RESPONSE:' + rid)
            rows[rid] = {**{k: plan[k] for k in identity}, 'response_id': rid, 'trial_id': trial,
                'run': root.name, 'model': key, 'target_model': model['model'],
                'dataset': original.get('generated_metadata', {}).get('provenance', {}).get('dataset', 'UNKNOWN'),
                'original_item_id': original['item_id'], 'answer': response.get('answer') if response else None,
                'action': action, 'target_status': saved.get('status', 'NOT_RUN'),
                'original_reference_match': match, 'reference_basis': 'ORIGINAL_REFERENCE_ONLY',
                'input_semantic_answerability': meta.get('semantic_answerability', 'NOT_ESTABLISHED'),
                'target_response_sha256': store.digest(response), 'review_status': 'NOT_REVIEWED',
                'assessment': None, 'independent_item_review': independent.get(plan['item_id'])}
            targets[rid] = response

    folder = root / '02_analysis/02_comparison'
    requests = snap.read(folder / 'manifest.jsonl', lines=True)
    unique(requests, 'trial_id')
    seen = set()
    for req in requests:
        path = snap.latest(folder, req['trial_id'])
        result = snap.read(path) if path else None
        status = result.get('status', 'NOT_RUN') if result else 'NOT_RUN'
        errors = []
        if path and snap.read(path.with_name('request.json')) != req:
            status = 'REQUEST_MISMATCH'
        if status == 'VALID':
            errors = contracts.validate_response(result.get('response'), req)
            if errors:
                status = 'CONTRACT_FAILED'
        assessments = unique(result['response'].get('response_assessments', []), 'response_id') if status == 'VALID' else {}
        for observed in req['input']['responses']:
            rid = observed['response_id']
            if rid not in rows:
                raise ValueError('ANALYSIS_RESPONSE_OUTSIDE_EVALUATION:' + rid)
            row = rows[rid]
            if any(row[k] != observed[k] for k in ('item_id', 'case', 'variant', 'model', 'prompt_condition', 'reasoning')):
                raise ValueError('ANALYSIS_IDENTITY_MISMATCH:' + rid)
            if observed['variant'] == 'ORIGINAL':
                continue  # Current A02 rubric never reviews original responses.
            if rid in seen:
                raise ValueError('DUPLICATE_ANALYSIS_TARGET:' + rid)
            seen.add(rid)
            assessment = assessments.get(rid)
            material = contracts.review_status(observed, req)
            review = assessment['review_status'] if assessment else material if material != 'COMPLETED' else (
                'NOT_REVIEWED' if status == 'NOT_RUN' else 'REVIEW_FAILED')
            actual_public = public[row['item_id']]
            observed_public = req['input'].get('inputs', {}).get(row['item_id'], {}).get('public', {})
            if any(actual_public.get(k) != observed_public.get(k) for k in ('question', 'context', 'answer_format')):
                review, assessment = 'STALE_INPUT', None
            if row['target_status'] != observed['status'] or targets[rid] != observed.get('response'):
                review, assessment = 'STALE_TARGET', None
            row.update(review_status=review, assessment=assessment, judge_call_status=status,
                analysis_trial_id=req['trial_id'], analysis_result=str(path.relative_to(root)) if path else None,
                judge_model=req['model'], judge_effort=req.get('reasoning_effort'), validation_errors=errors)
    for row in rows.values():
        if row['target_status'] != 'VALID':
            row['review_status'] = 'NOT_REVIEWABLE' if row['target_status'] != 'NOT_RUN' else 'NOT_RUN'
        elif row['variant'] == 'ORIGINAL':
            row['review_status'] = 'ORIGINAL_NOT_GROUNDING_REVIEWED'
        assessment = row['assessment'] or {}
        arv = assessment.get('abstention_reason_validity', {}).get('verdict')
        dg = assessment.get('decision_grounding', {}).get('verdict')
        item = row['independent_item_review']
        row.update(arv=arv, dg=dg, **classify(row['action'], row['review_status'], arv, dg,
                   row['original_reference_match'], item['value'] if item else None))
    snap.verify()
    return list(rows.values()), snap


def counts(rows):
    counter = Counter(r['semantic_answerability'] for r in rows)
    reviews = Counter(r['review_status'] for r in rows)
    return {'total': len(rows), **{c: counter[c] for c in CATEGORIES},
            'review_status': dict(reviews),
            'review_coverage': 'NO_COMPLETED_REVIEWS' if not reviews.get('COMPLETED') else 'PARTIAL_OR_ABSENT' if any(reviews.get(k) for k in (
                'NOT_REVIEWED', 'NOT_RUN', 'REVIEW_FAILED', 'STALE_INPUT', 'STALE_TARGET',
                'ORIGINAL_NOT_GROUNDING_REVIEWED')) else 'AVAILABLE_REVIEWS_COLLECTED',
            'unclassified_reasons': dict(Counter(r['classification_reason'] for r in rows if r['semantic_answerability'] == 'UNCLASSIFIED')),
            'nasu': dict(Counter(r['nasu'] for r in rows)),
            'independent_item_reviews': sum(r['independent_item_review'] is not None for r in rows)}


def summarize(root, rows, snap):
    scopes = {'all': rows, 'originals': [r for r in rows if r['variant'] == 'ORIGINAL'],
              'variants': [r for r in rows if r['variant'] != 'ORIGINAL'],
              'h1': [r for r in rows if r['variant'] in H1_VARIANTS]}
    groups = []
    for scope, selected in scopes.items():
        grouped = defaultdict(list)
        for row in selected:
            grouped[tuple(row[k] for k in ('model', 'dataset', 'prompt_condition', 'reasoning'))].append(row)
        for key, values in sorted(grouped.items()):
            groups.append({'scope': scope, **dict(zip(('model', 'dataset', 'prompt_condition', 'reasoning'), key)), **counts(values)})
    return {'schema_version': VERSION, 'run': root.name, 'generated_at': store.now(),
        'implementation_sha256': store.file_hash(__file__),
        'template_sha256': store.file_hash(Path(__file__).with_name('output-readme-template.md')),
        'status': 'CLASSIFIED', 'new_model_calls': 0, 'semantic_answerability_scope': 'RESPONSE_OUTCOME_NOT_ITEM_GOLD',
        'categories': LABELS, 'scopes': {key: counts(value) for key, value in scopes.items()}, 'groups': groups,
        'source_hashes': snap.files, 'latest_attempts': snap.attempts,
        'rules': {'supported_answer': 'Numeric + DG SUPPORTED', 'supported_abstention': 'Null + ARV/DG SUPPORTED',
            'unnecessary_abstention': 'Abstention + independent ANSWERABLE item review',
            'missed_abstention': 'Numeric + independent UNANSWERABLE item review',
            'unsupported_alone': 'UNCLASSIFIED; original-reference mismatch does not establish unanswerability',
            'originals': 'No current A02 grounding review; keep separate from variant denominators',
            'source_conflict': 'UNCLASSIFIED if independent item review contradicts a supported response review'}}


def markdown(summaries):
    text = ['# Results from five categories', '', 'So we sorted the existing Analysis determination into Python. 0entries.',
            'The unnecessary failure of the authority 0It doesn\'t mean that there\'s no case that\'s been confirmed by an explicit case judgment, and it doesn\'t imply that the action hasn\'t occurred.', '']
    text += ['The whole is the response number of the execution plan, included in the mismatched/unchecked/uncheckable subset, and should be read along with the completed review number.', '',
             '## All responses by model/original and 7variants', '',
             'Model-based answers, model-based mechanisms, unnecessary mechanisms, failure of mechanisms, mismatch, complete review.',
             '|---|---:|---:|---:|---:|---:|---:|---:|']
    models = defaultdict(list)
    for summary in summaries:
        for row in summary['groups']:
            if row['scope'] == 'all':
                models[row['model']].append(row)
    for model, groups in sorted(models.items()):
        totals = [sum(g[c] for g in groups) for c in (*CATEGORIES, 'total')]
        reviewed = sum(g['review_status'].get('COMPLETED', 0) for g in groups)
        text.append('| ' + model + ' | ' + ' | '.join(f'{n:,}' for n in (*totals, reviewed)) + ' |')
    text += ['', '## The timing and review status', '', 'Running the storage time, modification review, complete review, updated.', '|---|---|---:|---|---|']
    for summary in summaries:
        scope = summary['scopes']['variants']
        text.append(f"| {summary['run']} | {summary['generated_at']} | {scope['review_status'].get('COMPLETED', 0):,} / {scope['total']:,} | {scope['review_coverage']} | {summary.get('snapshot_status', 'SAVED_SNAPSHOT')} |")
    text += ['']
    for scope, name in (('h1', 'The H1 5variants'), ('variants', '7all variants'), ('originals', 'Original response')):
        text += ['## ' + name, '', 'Implementation / Model / Data-based answers / Data-driven mechanisms / Unnecessary mechanisms / Failure of mechanisms / Mismatch / Complete review', '|---|---:|---:|---:|---:|---:|---:|---:|']
        for summary in summaries:
            grouped = defaultdict(list)
            for row in summary['groups']:
                if row['scope'] == scope:
                    grouped[(row['model'], row['dataset'])].append(row)
            for (model, dataset), groups in grouped.items():
                totals = [sum(g[c] for g in groups) for c in (*CATEGORIES, 'total')]
                reviewed = sum(g['review_status'].get('COMPLETED', 0) for g in groups)
                text.append('| ' + f"{summary['run']} / {model} / {dataset}" + ' | ' + ' | '.join(f'{n:,}' for n in (*totals, reviewed)) + ' |')
        text += ['']
    text += ['## model / Prompt / Reasoning by H1', '', 'Implementation / Model / Data / Prompt / Reasoning based on answers / Based on mechanisms / Unnecessary mechanisms / Failure of mechanisms / Mismatch', '|---|---|---|---:|---:|---:|---:|---:|---:|']
    for summary in summaries:
        for row in summary['groups']:
            if row['scope'] == 'h1':
                text.append('| ' + f"{summary['run']} / {row['model']} / {row['dataset']}" + f" | {row['prompt_condition']} | {row['reasoning']} | " + ' | '.join(f'{row[c]:,}' for c in (*CATEGORIES, 'total')) + ' |')
    return '\n'.join(text) + '\n'


def build(root):
    root = Path(root).resolve()
    with store.locked(root / '.semantic-answerability.lock'):
        rows, snap = extract(root)
        summary = summarize(root, rows, snap)
        output = root / OUTPUT
        previous = store.read(output / 'summary.json')
        if (previous and previous.get('schema_version') == VERSION and previous.get('source_hashes') == snap.files
                and previous.get('latest_attempts') == snap.attempts
                and previous.get('implementation_sha256') == summary['implementation_sha256']
                and previous.get('template_sha256') == summary['template_sha256']):
            if all((output / p).is_file() and store.file_hash(output / p) == h for p, h in previous.get('output_hashes', {}).items()) and previous.get('output_hashes'):
                return previous
        # Preserve each previous derived version before replacing the current one.
        if previous:
            history = output / 'history' / store.digest(previous)[:16]
            for name in ('responses.jsonl', 'summary.json', 'summary.md', 'README.md'):
                path = output / name
                if path.exists():
                    store.write_text(history / name, path.read_text())
        snap.verify()
        store.write_rows(output / 'responses.jsonl', rows)
        store.write_text(output / 'summary.md', markdown([summary]))
        template = Path(__file__).with_name('output-readme-template.md').read_text()
        store.write_text(output / 'README.md', template.replace('{{run}}', root.name))
        summary['output_hashes'] = {p: store.file_hash(output / p) for p in ('responses.jsonl', 'summary.md', 'README.md')}
        store.write(output / 'summary.json', summary)
        store.event(root, 'SEMANTIC_RESPONSE_OUTCOMES_CLASSIFIED', processor='PYTHON', new_model_calls=0,
                    total=len(rows), counts=summary['scopes']['variants'], schema_version=VERSION)
        return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='append', default=[], help='Repeat for multiple saved runs.')
    parser.add_argument('--runs-file', type=Path, help='Existing H1 registry JSON with a runs array.')
    parser.add_argument('--repo', type=Path, default=store.PROJECT)
    parser.add_argument('--report', type=Path, help='Combined model tables as Markdown and JSON.')
    args = parser.parse_args()
    roots = [Path(p) for p in args.run]
    if args.runs_file:
        roots += [args.repo / 'reports/experiments-run' / r['run'] for r in store.read(args.runs_file)['runs']]
    if not roots:
        parser.error('Provide --run or --runs-file.')
    summaries, failures = [], []
    for root in dict.fromkeys(p.resolve() for p in roots):
        try:
            summary = build(root)
        except (ValueError, OSError, RuntimeError) as error:
            failure = {'run': root.name, 'status': 'NOT_PUBLISHED', 'reason': str(error)}
            failures.append(failure)
            previous = store.read(root / OUTPUT / 'summary.json')
            if previous and previous.get('schema_version') == VERSION and previous.get('output_hashes') and all(
                    (root / OUTPUT / name).is_file() and store.file_hash(root / OUTPUT / name) == digest
                    for name, digest in previous['output_hashes'].items()):
                summaries.append(previous | {'snapshot_status': 'PREVIOUS_SNAPSHOT_NOT_REFRESHED',
                                              'refresh_error': str(error)})
            print(json.dumps(failure), flush=True)
            continue
        summaries.append(summary)
        print(json.dumps({'run': root.name, 'h1': summary['scopes']['h1'], 'variants': summary['scopes']['variants'], 'new_model_calls': 0}, ensure_ascii=False), flush=True)
    if args.report:
        report = markdown(summaries)
        if failures:
            report += '\n## The estimate is unsuccessful run\n\n' + '\n'.join(f"- {r['run']}: {r['reason']}" for r in failures) + '\n'
        store.write_text(args.report, report)
        store.write(args.report.with_suffix('.json'), {'schema_version': VERSION, 'runs': summaries,
                                                     'not_published': failures, 'new_model_calls': 0})
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
