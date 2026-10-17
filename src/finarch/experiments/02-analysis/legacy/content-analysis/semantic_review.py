"""A01: Native Batch input assessment, blinded response review, and fixed metrics."""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import json
from pathlib import Path

run_layout = __import__('finarch.experiments.90-operations.run_layout', fromlist=['*'])
import random

store = __import__('finarch.experiments.90-operations.storage', fromlist=['*'])
batch = __import__('finarch.experiments.01-evaluation.03-execution.openai_batch', fromlist=['*'])
contract = __import__('finarch.experiments.02-analysis.legacy.content-analysis.semantic_contract', fromlist=['*'])
answer_contract = __import__('finarch.experiments.01-evaluation.02-request.answer_contract', fromlist=['*'])
pipeline = __import__('finarch.experiments.01-evaluation.pipeline', fromlist=['*'])
ROOT = Path('02_analysis/01_response_review')
SUPPORTED = {'SUPPORTED_ANSWER', 'SUPPORTED_CONDITIONAL_OR_ABSTENTION'}


def model_for(root):
    config = run_layout.analysis_config(root)
    if not config.get('enabled'):
        # Legacy artifacts can be read, but new analysis must be explicitly selected.
        raise ValueError('ANALYSIS_BACKEND_MUST_BE_CONFIGURED_AND_ENABLED')
    backend = config.get('backend')
    if backend not in ('api', 'codex'):
        raise ValueError('ANALYSIS_BACKEND_MUST_BE_API_OR_CODEX')
    selected = deepcopy(config.get('backends', {}).get(backend, {}))
    if not selected.get('model') or not selected.get('reasoning_effort'):
        raise ValueError('ANALYSIS_MODEL_AND_REASONING_REQUIRED')
    selected.update(transport='openai_batch' if backend == 'api' else 'codex_cli',
                    schedule=config.get('schedule', {}), backend=backend)
    return selected


def body_for(model, request):
    """Send only the blinded assessment payload, prompt, and strict schema."""
    return {'model': model['model'], 'instructions': request['prompt'],
            'input': [{'role': 'user', 'content': [{'type': 'input_text', 'text': store.encoded(request['input']).decode()}]}],
            'reasoning': {'effort': request['reasoning_effort']},
            'text': {'format': {'type': 'json_schema', 'name': 'financial_review', 'strict': True,
                                'schema': request['response_schema']}},
            'max_output_tokens': request['max_output_tokens'], 'store': False, 'tools': [],
            'truncation': 'disabled', 'prompt_cache_options': {'mode': 'explicit'}}


def freeze_contract(root, source_run=None):
    """Freeze the same assessment criteria across all development rounds."""
    base = Path(root) / ROOT
    definition = base / '00-definition'
    if (definition / 'manifest.json').exists():
        for name, sha in store.read(definition / 'manifest.json').items():
            if store.file_hash(definition / name) != sha:
                raise ValueError('FROZEN_REVIEW_CONTRACT_CHANGED:' + name)
        return definition
    definition.mkdir(parents=True, exist_ok=True)
    if source_run:
        source = freeze_contract(Path(source_run))
        for name in store.read(source / 'manifest.json'):
            store.write_text(definition / name, (source / name).read_text())
    else:
        source = store.PROJECT / 'experiment/archtecture/analysis'
        for name in ('input-review.md', 'response-review.md'):
            store.write_text(definition / name, (source / name).read_text())
        store.write(definition / 'input.schema.json', contract.INPUT_SCHEMA)
        store.write(definition / 'response.schema.json', contract.RESPONSE_SCHEMA)
    store.write(definition / 'manifest.json', {p.name: store.file_hash(p) for p in definition.iterdir() if p.is_file()})
    return definition


def request_for(root, item, stage, data, definition):
    selected = model_for(root)
    request = {'item_id': item['item_id'], 'stage': stage, 'model': selected['model'],
               'reasoning_effort': selected['reasoning_effort'],
               'prompt': (definition / f'{stage}-review.md').read_text(),
               'response_schema': store.read(definition / f'{stage}.schema.json'), 'input': data}
    if selected['transport'] == 'openai_batch':
        request['max_output_tokens'] = selected.get('max_output_tokens', 65536)
    request['trial_id'] = store.digest({'run': Path(root).name, **request})[:32]
    return request


def prepare_input(root):
    root = Path(root).resolve()
    pipeline.verify(root)
    definition = freeze_contract(root)
    folder = root / ROOT / '01-LLM-input'
    manifest = folder / 'manifest.jsonl'
    if not manifest.exists():
        requests = [request_for(root, item, 'input', {k: item[k] for k in ('question', 'context', 'answer_format')}, definition)
                    for item in store.rows(run_layout.inputs(root) / 'public.jsonl')]
        store.write_rows(manifest, requests)
        store.event(root, 'INPUT_REVIEW_PREPARED', requests=len(requests), target_responses_visible=False)
    return folder


def checked_results(folder):
    folder = Path(folder)
    state = store.read(folder / 'state.json', {})
    if state.get('status') != 'COLLECTED':
        raise ValueError('REVIEW_RESULTS_NOT_COLLECTED')
    for name, sha in state['output_hashes'].items():
        if store.file_hash(folder / name) != sha:
            raise ValueError('REVIEW_SOURCE_CHANGED:' + name)
    if any(state.get('statuses', {}).get(status, 0) for status in batch.policy.STOP_STATUSES):
        raise ValueError('REVIEW_CACHE_POLICY_BLOCKED_STOP_NEW_CALLS')
    return store.rows(folder / 'results.jsonl')


def effective_results(folder):
    """Keep first attempts immutable; use one separately recorded recovery only."""
    folder = Path(folder)
    original = checked_results(folder)
    retry = folder / 'retry-001'
    if store.read(retry / 'state.json', {}).get('status') != 'COLLECTED':
        return original
    corrected = {r['item_id']: r for r in checked_results(retry)}
    return [corrected.get(r['item_id'], r) if r['status'] != 'VALID' else r for r in original]


def recover_stage(root, folder):
    """One native Batch retry for technical/schema failures, never semantic scores."""
    root, folder = Path(root), Path(folder)
    original = checked_results(folder)
    failed = {r['trial_id']: r for r in original if r['status'] in ('OUTPUT_TRUNCATED', 'INVALID_RESPONSE', 'BATCH_REQUEST_ERROR', 'BATCH_REQUEST_MISSING')}
    if run_layout.analysis_config(root).get('technical_retry_limit', 1) < 1:
        return {'status': 'RETRY_DISABLED', 'requests': 0}
    if not failed:
        return {'status': 'COLLECTED', 'requests': 0}
    retry = folder / 'retry-001'
    manifest = retry / 'manifest.jsonl'
    if not manifest.exists():
        requests = []
        for first in store.rows(folder / 'manifest.jsonl'):
            if first['trial_id'] not in failed:
                continue
            request = deepcopy(first)
            if model_for(root)['transport'] == 'openai_batch':
                request['max_output_tokens'] = min(128000, max(65536, first['max_output_tokens'] * 2))
            request['retry_of'] = first['trial_id']
            request['trial_id'] = store.digest(request)[:32]
            requests.append(request)
        store.write_rows(manifest, requests)
        store.event(root, 'SEMANTIC_TECHNICAL_RETRY_PREPARED', stage=folder.name, requests=len(requests),
                    reason='OUTPUT_LIMIT_OR_CONTRACT_FAILURE_ONLY', maximum_attempts=2)
    return run_stage(root, retry)


def prepare_response(root, input_run=None, audit=False):
    """Review only locally valid solver outputs; leave other rows unassessed."""
    root = Path(root).resolve()
    input_run = Path(input_run).resolve() if input_run else root
    pipeline.verify(root)
    if store.read(root / 'state.json')['status'] != 'FINISHED':
        raise ValueError('SOLVER_COLLECTION_MUST_FINISH_BEFORE_REVIEW')
    if store.file_hash(run_layout.inputs(root) / 'public.jsonl') != store.file_hash(run_layout.inputs(input_run) / 'public.jsonl'):
        raise ValueError('INPUT_REVIEW_COHORT_MISMATCH')
    definition = freeze_contract(root, input_run if input_run != root else None)
    source = input_run / ROOT / '01-LLM-input'
    input_records = {r['item_id']: r for r in effective_results(source)}
    model = store.configuration(root)['models'][0]
    public = {r['item_id']: r for r in store.rows(run_layout.inputs(root) / 'public.jsonl')}
    solver = store.rows(run_layout.validation(root, model['key']) / 'results.jsonl')
    folder = root / ROOT / ('03-LLM-audit' if audit else '02-LLM-response')
    manifest = folder / 'manifest.jsonl'
    if manifest.exists():
        return folder
    audit_ids = None
    if audit:
        first = effective_results(root / ROOT / '02-LLM-response')
        by_outcome = defaultdict(list)
        for result in first:
            if result['status'] == 'VALID':
                request = result['identity_map']
                for review in result['response']['reviews']:
                    by_outcome[review['outcome']].append(request[review['response_id']]['trial_id'])
        audit_ids = set()
        for outcome, ids in sorted(by_outcome.items()):
            ordered = sorted(ids, key=lambda key: store.digest({'trial': key, 'purpose': 'balanced-audit-v1'}))
            audit_ids.update(ordered[:8])
    grouped, skipped = defaultdict(list), []
    for row in solver:
        item_id = row['item_id']
        assessment = input_records.get(item_id, {})
        if row['status'] != 'VALID' or assessment.get('status') != 'VALID':
            skipped.append({'trial_id': row['trial_id'], 'reason': 'SOLVER_NOT_VALID' if row['status'] != 'VALID' else 'INPUT_REVIEW_NOT_VALID'})
            continue
        if audit_ids is not None and row['trial_id'] not in audit_ids:
            continue
        result = store.read(root / row['result_path'])
        grouped[item_id].append((row, result['response']))
    requests = []
    for item_id, entries in grouped.items():
        # Stable randomized order; IDs do not disclose conditions or reasoning.
        entries.sort(key=lambda pair: store.digest({'trial': pair[0]['trial_id'], 'audit': audit}))
        data = {k: public[item_id][k] for k in ('question', 'context', 'answer_format')}
        data['input_assessment'] = input_records[item_id]['response']
        data['responses'] = [{'response_id': f'response-{index + 1}', 'response': response}
                             for index, (_, response) in enumerate(entries)]
        request = request_for(root, public[item_id], 'response', data, definition)
        if audit:
            request['reasoning_effort'] = model_for(root)['reasoning_effort']
            request['prompt'] += '\nThis is an independent quality audit. Recompute every conclusion without seeing another response-review verdict. Do not defer to the provisional input assessment.\n'
        request['trial_id'] = store.digest({'audit': audit, **request})[:32]
        request['identity_map'] = {f'response-{index + 1}': {k: row[k] for k in ('trial_id', 'item_id', 'case', 'variant', 'experiment', 'prompt_condition', 'reasoning', 'result_path')}
                                   for index, (row, _) in enumerate(entries)}
        request['input_review_source'] = {'run': input_run.name, 'path': str(source.relative_to(input_run) / 'results.jsonl'),
                                          'sha256': store.file_hash(source / 'results.jsonl'),
                                          'recovery_sha256': store.file_hash(source / 'retry-001/results.jsonl') if (source / 'retry-001/results.jsonl').exists() else None}
        request['solver_source_hashes'] = {row['result_path']: store.file_hash(root / row['result_path']) for row, _ in entries}
        requests.append(request)
    store.write_rows(manifest, requests)
    store.event(root, 'REVIEW_SELECTION', stage=folder.name, skipped=skipped, solver_planned=len(solver),
        requests=len(requests), responses=sum(len(r['identity_map']) for r in requests),
        audit_selection='UP_TO_EIGHT_PER_OBSERVED_OUTCOME_NOT_POPULATION_REPRESENTATIVE' if audit else None)
    store.event(root, 'RESPONSE_REVIEW_PREPARED', requests=len(requests), audit=audit, conditions_blinded=True)
    return folder


def run_stage(root, folder):
    """One durable submission/status check/collection; safe to call on wakeup."""
    root, folder = Path(root).resolve(), Path(folder).resolve()
    model = model_for(root)
    with store.locked(folder / '.review.lock'):
        previous = store.read(folder / 'state.json', {})
        if previous.get('status') == 'COLLECTED':
            checked_results(folder)
            return previous
        manifest = folder / 'manifest.jsonl'
        requests = store.rows(manifest)
        if not requests:
            store.write_rows(folder / 'results.jsonl', [])
            state = {'status': 'COLLECTED', 'requests': 0, 'statuses': {}, 'token_cost_estimate_usd': 0,
                     'requests_without_known_cost': 0, 'output_hashes': {'results.jsonl': store.file_hash(folder / 'results.jsonl')}}
            store.write(folder / 'state.json', state)
            return state
        if model['transport'] == 'codex_cli':
            runner = __import__('finarch.experiments.02-analysis.legacy.content-analysis.codex_review', fromlist=['run'])
            result = runner.run(root, folder, requests, model)
            render_readme(root)
            return result
        job_folder = folder / 'batch-001'
        batch.prepare_job(model, manifest, job_folder, requests, body_for)
        job = batch.submit(model, job_folder)
        job = batch.poll(model, job_folder)
        state = {'status': 'BATCH_PENDING', 'batch_id': job['batch_id'], 'provider_status': job['provider']['status'],
                 'request_counts': job['provider'].get('request_counts'), 'requests': len(requests),
                 'updated_at': store.now(), 'billed_cost_usd': None, 'token_cost_estimate_usd': None}
        if job['provider']['status'] in batch.TERMINAL:
            records = batch.outputs(job_folder, {r['trial_id'] for r in requests})
            results = []
            for request in requests:
                found = records.get(request['trial_id'])
                result = batch.interpret(model, request, found[0], contract.validate) if found else {
                    'status': 'BATCH_REQUEST_MISSING', 'usage': None, 'token_cost_estimate_usd': None}
                result.update(trial_id=request['trial_id'], item_id=request['item_id'], stage=request['stage'],
                              identity_map=request.get('identity_map', {}), batch_id=job['batch_id'])
                results.append(result)
            store.write_rows(folder / 'results.jsonl', results)
            state.update(status='COLLECTED', statuses=dict(Counter(r['status'] for r in results)),
                         token_cost_estimate_usd=round(sum(r.get('token_cost_estimate_usd') or 0 for r in results), 10),
                         requests_without_known_cost=sum(r.get('token_cost_estimate_usd') is None for r in results),
                         output_hashes={name: store.file_hash(folder / name) for name in ['manifest.jsonl', 'results.jsonl']})
            state['output_hashes'].update({str(p.relative_to(folder)): store.file_hash(p) for p in job_folder.glob('*.jsonl')})
            job.update(status='COLLECTED', collected_at=store.now(), result_status='COLLECTED')
            store.write(job_folder / 'job.json', job)
            store.event(root, 'SEMANTIC_BATCH_COLLECTED', stage=folder.name, **{k: state[k] for k in ('requests', 'statuses', 'token_cost_estimate_usd')})
        store.write(folder / 'state.json', state)
        render_readme(root)
        if state['status'] == 'COLLECTED':
            checked_results(folder)
        return state


def rows_for(root, input_run=None):
    root = Path(root).resolve()
    input_run = Path(input_run).resolve() if input_run else root
    independent = {r['item_id']: r for r in effective_results(input_run / ROOT / '01-LLM-input')}
    primary, audits = {}, {}
    for stage, index in [('02-LLM-response', primary), ('03-LLM-audit', audits)]:
        folder = root / ROOT / stage
        if store.read(folder / 'state.json', {}).get('status') != 'COLLECTED':
            continue
        for result in effective_results(folder):
            for review in result.get('response', {}).get('reviews', []) if result['status'] == 'VALID' else []:
                identity = result['identity_map'][review['response_id']]
                index[identity['trial_id']] = {**review, 'judge_trial_id': result['trial_id']}
    config = store.configuration(root)
    diagnostics = {r['trial_id']: r for r in store.rows(run_layout.diagnostics(root) / 'response-diagnostics.jsonl')}
    output = []
    for model in config['models']:
        for row in store.rows(run_layout.validation(root, model['key']) / 'results.jsonl'):
            trial = row['trial_id']
            input_result = independent.get(row['item_id'], {})
            review, audit = primary.get(trial), audits.get(trial)
            payload = store.read(root / row['result_path'], {}).get('response') if row.get('result_path') else None
            declared = answer_contract.declaration(payload)
            stated, mode = declared['classification'], declared['mode']
            label_present = stated in answer_contract.CLASSIFICATIONS
            is_guided = run_layout.prompt_condition(row['prompt_condition']) == 'guided'
            explicit = declared['source'] == 'JSON_FIELD'
            classification = input_result.get('response', {}).get('classification') if input_result.get('status') == 'VALID' else None
            disagreement = bool(review and audit and any(review[k] != audit[k] for k in ('outcome', 'calculation', 'grounding', 'consistency')))
            assessed = bool(review and review['outcome'] != 'UNRESOLVED' and not disagreement)
            output.append({k: row[k] for k in ('trial_id', 'item_id', 'case', 'variant', 'experiment', 'prompt_condition', 'reasoning', 'status', 'result_path')})
            output[-1].update(model=model['key'], input_classification=classification,
                stated_classification=stated, stated_mode=mode, classification_source=declared['source'],
                guided_label_present=label_present if is_guided else None,
                guided_classification_answer_consistent=((stated == 'ANSWERABLE') == (type(payload.get('answer')) in (int, float)))
                    if is_guided and explicit and label_present and row['status'] == 'VALID' else None,
                guided_mode_answer_consistent=((mode == 'ANSWER') == (payload.get('answer') is not None))
                    if is_guided and mode and row['status'] == 'VALID' else None,
                guided_mode_behavior_matches=(mode == review['behavior'])
                    if is_guided and mode and review else None,
                guided_classification_matches_input=(stated == classification)
                    if is_guided and stated in contract.STATES and classification else None,
                original_numeric_match=((diagnostics.get(trial, {}).get('numeric_comparison') if run_layout.ordered(root) else row.get('checks', {}).get('numeric_comparison')) or {}).get('matches'),
                review=review, audit=audit, audit_disagreement=disagreement, semantic_assessed=assessed,
                appropriate=review['outcome'] in SUPPORTED if assessed else None,
                unassessed_reason=None if assessed else 'AUDIT_DISAGREEMENT' if disagreement else 'UNRESOLVED' if review else 'SOLVER_OR_JUDGE_NOT_VALID')
    return output


def cell(rows):
    assessed = [r for r in rows if r['semantic_assessed']]
    audited = [r for r in rows if r.get('review') and r.get('audit')]
    verdict = lambda v: 'UNRESOLVED' if v['outcome'] == 'UNRESOLVED' else 'APPROPRIATE' if v['outcome'] in SUPPORTED else 'INAPPROPRIATE'
    return {'planned': len(rows), 'format_valid': sum(r['status'] == 'VALID' for r in rows),
            'assessed': len(assessed), 'unassessed': len(rows) - len(assessed),
            'appropriate': sum(r['appropriate'] is True for r in assessed),
            'appropriate_rate_assessed': sum(r['appropriate'] is True for r in assessed) / len(assessed) if assessed else None,
            'planned_worst_best_bounds': [sum(r['appropriate'] is True for r in assessed) / len(rows),
                (sum(r['appropriate'] is True for r in assessed) + len(rows) - len(assessed)) / len(rows)] if rows else None,
            'outcomes': dict(Counter(r['review']['outcome'] if r['review'] else 'NOT_REVIEWED' for r in rows)),
            'observed_behaviors': dict(Counter(r['review']['behavior'] if r['review'] else 'NOT_REVIEWED' for r in rows)),
            'appropriate_behaviors': dict(Counter(r['review']['behavior'] for r in assessed if r['appropriate'])),
            'dimension_failures': {key: sum(bool(r['review'] and r['review'].get(key) == 'FAIL') for r in rows) for key in ('calculation', 'grounding', 'consistency')},
            'audit_disagreements': sum(r['audit_disagreement'] for r in rows),
            'audit_reviewed': len(audited),
            'audit_appropriateness_disagreements': sum(verdict(r['review']) != verdict(r['audit']) for r in audited),
            'audit_outcome_disagreements': sum(r['review']['outcome'] != r['audit']['outcome'] for r in audited),
            'numeric_matches': sum(r['original_numeric_match'] is True for r in rows),
            'numeric_compared': sum(r['original_numeric_match'] is not None for r in rows),
            'guided_planned': sum(run_layout.prompt_condition(r['prompt_condition']) == 'guided' for r in rows),
            'guided_labels_present': sum(r.get('guided_label_present') is True for r in rows),
            'guided_classification_sources': dict(Counter(r.get('classification_source') or 'NOT_STATED' for r in rows if run_layout.prompt_condition(r['prompt_condition']) == 'guided')),
            'guided_stated_classifications': dict(Counter(r.get('stated_classification') or 'NOT_STATED' for r in rows if run_layout.prompt_condition(r['prompt_condition']) == 'guided')),
            'guided_classification_answer_checked': sum(r.get('guided_classification_answer_consistent') is not None for r in rows),
            'guided_classification_answer_mismatches': sum(r.get('guided_classification_answer_consistent') is False for r in rows),
            'guided_mode_answer_checked': sum(r.get('guided_mode_answer_consistent') is not None for r in rows),
            'guided_mode_answer_mismatches': sum(r.get('guided_mode_answer_consistent') is False for r in rows),
            'guided_mode_behavior_compared': sum(r.get('guided_mode_behavior_matches') is not None for r in rows),
            'guided_mode_behavior_mismatches': sum(r.get('guided_mode_behavior_matches') is False for r in rows),
            'guided_stated_modes': dict(Counter(r.get('stated_mode') or 'NOT_STATED' for r in rows if run_layout.prompt_condition(r['prompt_condition']) == 'guided')),
            'guided_classification_compared': sum(r.get('guided_classification_matches_input') is not None for r in rows),
            'guided_classification_matches': sum(r.get('guided_classification_matches_input') is True for r in rows)}


def paired(rows, axis, left, right):
    """Paired development differences with original-case cluster bootstrap."""
    axes = [key for key in ('model', 'case', 'variant', 'prompt_condition', 'reasoning') if key != axis]
    indices = []
    for value in (left, right):
        index = {}
        for row in rows:
            if (run_layout.prompt_condition(row[axis]) if axis == 'prompt_condition' else row[axis]) != (run_layout.prompt_condition(value) if axis == 'prompt_condition' else value):
                continue
            key = tuple(row.get(k, '') for k in axes)
            if key in index:
                raise ValueError('DUPLICATE_ANALYSIS_CONDITION')
            index[key] = row
        indices.append(index)
    keys = sorted(set(indices[0]) | set(indices[1]))
    pairs, missing, counts, clusters = [], 0, Counter(), defaultdict(list)
    for key in keys:
        a, b = indices[0].get(key), indices[1].get(key)
        if not a or not b or not a['semantic_assessed'] or not b['semantic_assessed']:
            missing += 1
            continue
        counts[f'{int(a["appropriate"])}->{int(b["appropriate"])}'] += 1
        delta = int(b['appropriate']) - int(a['appropriate'])
        clusters[a['case']].append(delta)
        pairs.append({'left': a['trial_id'], 'right': b['trial_id'], 'model': a.get('model'),
                      'case': a['case'], 'variant': a['variant'], 'delta': delta})
    values = list(clusters.values())
    confidence = None
    if len(values) > 1:
        rng = random.Random(20260927)
        samples = []
        for _ in range(2000):
            sample = [v for _ in values for v in rng.choice(values)]
            samples.append(sum(sample) / len(sample))
        samples.sort()
        confidence = [samples[49], samples[1949]]
    return {'axis': axis, 'left': left, 'right': right, 'planned_pairs': len(keys), 'assessed_pairs': len(pairs),
            'unassessed_pairs': missing, 'transitions': dict(counts), 'original_clusters': len(values),
            'difference': sum(p['delta'] for p in pairs) / len(pairs) if pairs else None,
            'cluster_bootstrap_95': confidence, 'scope': 'EXPLORATORY_NOT_CONFIRMATORY', 'pairs': pairs}


def build(root, input_run=None):
    root = Path(root).resolve()
    rows = rows_for(root, input_run)
    folder = root / '02_analysis/02_comparison'
    matrices = []
    groups = defaultdict(list)
    for row in rows:
        groups[(row['model'], row['variant'], row['prompt_condition'], row['reasoning'])].append(row)
    for (model, variant, prompt, reasoning), group in sorted(groups.items()):
        matrices.append({'model': model, 'variant': variant, 'prompt': prompt, 'reasoning': reasoning, **cell(group)})
    control_key = lambda row: tuple(row[key] for key in ('model', 'case', 'prompt_condition', 'reasoning'))
    originals = {}
    for row in rows:
        if row['variant'] != 'ORIGINAL':
            continue
        key = control_key(row)
        if key in originals:
            raise ValueError('DUPLICATE_ORIGINAL_CONTROL_CONDITION')
        originals[key] = row
    relations = defaultdict(list)
    counterexamples = []
    missing_originals = []
    for row in rows:
        if row['variant'] == 'ORIGINAL':
            continue
        original = originals.get(control_key(row))
        if original is None:
            missing_originals.append(row)
        numeric = original['original_numeric_match'] if original else None
        group = ('ORIGINAL_CONDITION_MISSING' if original is None else 'ORIGINAL_NUMERIC_MATCH'
                 if numeric is True else 'ORIGINAL_NUMERIC_MISMATCH' if numeric is False else 'ORIGINAL_UNASSESSED')
        row.update(original_trial_id=original['trial_id'] if original else None,
                   original_control_status='MATCHED' if original else 'MISSING_SAME_CONDITION',
                   original_control_numeric_match=numeric,
                   original_control_semantic_assessed=bool(original and original['semantic_assessed']),
                   original_control_appropriate=original['appropriate'] if original else None)
        relations[(row['model'], group, row['prompt_condition'], row['reasoning'])].append(row)
        if original and row['semantic_assessed'] and ((numeric is True and not row['appropriate']) or (numeric is False and row['appropriate'])):
            counterexamples.append({'original_trial_id': original['trial_id'], **row})
    pairs = []
    for model in sorted({row['model'] for row in rows}):
        model_rows = [r for r in rows if r['model'] == model]
        pairs += [{**paired([r for r in model_rows if r['reasoning'] == reasoning and r['experiment'] == 2], 'prompt_condition', 'unguided', 'guided'), 'fixed_conditions': {'model': model, 'reasoning': reasoning}} for reasoning in ('off', 'on')]
        pairs += [{**paired([r for r in model_rows if run_layout.prompt_condition(r['prompt_condition']) == prompt], 'reasoning', 'off', 'on'), 'fixed_conditions': {'model': model, 'prompt': prompt}} for prompt in run_layout.PROMPT_FILES]
    review_states = {str(p.parent.relative_to(root / ROOT)): store.read(p) for p in (root / ROOT).rglob('state.json')}
    summary = {'run': root.name, 'updated_at': store.now(), 'overall': cell(rows), 'matrix': matrices,
               'original_variant_relations': [{'model': key[0], 'original_group': key[1], 'prompt': key[2], 'reasoning': key[3], **cell(group)} for key, group in sorted(relations.items())],
               'original_control_coverage': {'matching_fields': ['model', 'case', 'prompt_condition', 'reasoning'],
                   'variant_requests': sum(r['experiment'] == 2 for r in rows),
                   'missing_same_condition': len(missing_originals)},
               'paired': [{k: v for k, v in p.items() if k != 'pairs'} for p in pairs],
               'counterexample_count': len(counterexamples), 'review_stages': review_states, 'analysis_config': run_layout.analysis_config(root),
               'limitations': ['DEVELOPMENT_COHORT_REUSED', 'AUTOMATED_JUDGMENTS_NOT_HUMAN_GOLD',
                  'AUDIT_STRATIFIED_NOT_RANDOM_POPULATION_ESTIMATE',
                  'CHANGED_PROMPTS_ARE_NOT_IDENTICAL_REQUEST_REPEATS', 'NO_HUMAN_GOLD_SEMANTIC_LABELS']}
    if missing_originals:
        summary['limitations'].append('MISSING_SAME_CONDITION_ORIGINAL_CONTROL')
    if any(run_layout.prompt_condition(r['prompt_condition']) == 'guided' for r in missing_originals):
        summary['limitations'].append('NO_GUIDED_ORIGINAL_CONTROL')
    store.write_rows(folder / 'rows.jsonl', rows)
    store.write_rows(folder / 'counterexamples.jsonl', counterexamples)
    store.write(folder / 'paired.json', pairs)
    store.write(folder / 'summary.json', summary)
    store.event(root, 'SEMANTIC_ANALYSIS_BUILT', planned=len(rows), assessed=summary['overall']['assessed'], counterexamples=len(counterexamples))
    render_readme(root)
    return summary


def render_readme(root):
    root = Path(root)
    template = store.PROJECT / 'src/finarch/experiments/templates/semantic-review-readme.md'
    states = []
    for p in sorted((root / ROOT).rglob('state.json')):
        state = store.read(p)
        states.append(f"|{p.parent.relative_to(root / ROOT)}|{state['status']}|{state.get('requests', 0)}|{state.get('token_cost_estimate_usd', 'Waiting')}|")
    if run_layout.ordered(root):
        template = store.PROJECT / 'src/finarch/experiments/templates/ordered-analysis-readme.md'
    config = run_layout.analysis_config(root)
    backend = config.get('backend', 'Unknown.')
    selected = config.get('backends', {}).get(backend, {})
    text = template.read_text().replace('{{run}}', root.name).replace('{{states}}', '\n'.join(states))
    text = text.replace('{{backend}}', backend).replace('{{model}}', selected.get('model', 'Unknown.')).replace('{{effort}}', selected.get('reasoning_effort', 'Unknown.'))
    store.write_text(root / ROOT / 'README.md', text)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['input', 'response', 'audit', 'build'])
    parser.add_argument('--run', required=True)
    parser.add_argument('--input-run')
    args = parser.parse_args()
    root = Path(args.run)
    if args.action == 'build':
        result = build(root, args.input_run)
        print(json.dumps(result['overall']))
    else:
        folder = prepare_input(root) if args.action == 'input' else prepare_response(root, args.input_run, audit=args.action == 'audit')
        print(json.dumps(run_stage(root, folder)))
