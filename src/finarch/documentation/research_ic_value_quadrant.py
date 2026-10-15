"""Collect seven saved variant comparisons by dataset and identical input cohort."""
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'outputs/research/20260930-ic-value-quadrant'
LOG = ROOT / 'log/research-ic-value-quadrant/20260930'
TEMPLATES = Path(__file__).parent / 'templates/research'
INLINE = Path('/Users/wooix/.codex/visualizations/2026/09/20/01a0bd11-d386-7332-9187-10251c333670/ic-value-quadrant-comparison.html')
FEATURE = 'IC_VALUE_01_BEFORE'
CHOICES = ('A', 'B', 'OTHER', 'NULL', 'FORMAT_OR_EXECUTION_FAILED')
EA_CHOICES = ('ORIGINAL_VALUE', 'OTHER', 'NULL', 'FORMAT_OR_EXECUTION_FAILED')
FEATURES = (
    {'key': FEATURE, 'label': '01 · IC-value 앞', 'choices': CHOICES},
    {'key': 'IC_VALUE_01_AFTER', 'label': '02 · IC-value 뒤', 'choices': CHOICES},
    {'key': 'IC_SOURCE_A_ONLY', 'label': '03 · IC-source A', 'choices': CHOICES},
    {'key': 'IC_SOURCE_B_ONLY', 'label': '04 · IC-source B', 'choices': CHOICES},
    {'key': 'IC_RELATION_01', 'label': '05 · IC-relation', 'choices': CHOICES},
    {'key': 'EA_01', 'label': '06 · EA-01', 'choices': EA_CHOICES},
    {'key': 'EA_02', 'label': '07 · EA-02', 'choices': EA_CHOICES},
)
FEATURE_INDEX = {feature['key']: feature for feature in FEATURES}
CONDITIONS = ('unguided/off', 'unguided/on', 'guided/off', 'guided/on')
CONTRACT_FILES = ('common.md', 'prompt-unguided.md', 'prompt-guided.md', 'response.schema.json')
MODEL_STYLES = {
    'gpt-6-luna': ('luna', 'Luna', '#7860b0', 0),
    'claude-haiku-4-5-20251001': ('haiku', 'Haiku 4.5', '#247f76', 1),
    'Qwen/Qwen3-14B': ('qwen3-14b', 'Qwen3 14B', '#b66b38', 2),
    'Qwen/Qwen3-8B': ('qwen3-8b', 'Qwen3 8B', '#4775ac', 3),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def dataset_family(names):
    """Use source provenance, not the sometimes stale experiment input_path."""
    families = {('FinanceReasoning' if name.startswith('FinanceReasoning') else name) for name in names}
    require(len(families) == 1 and '' not in families, 'DATASET_PROVENANCE_MIXED_OR_MISSING')
    return next(iter(families))


def model_style(model_id):
    if model_id in MODEL_STYLES:
        key, label, color, order = MODEL_STYLES[model_id]
    else:
        key = 'model-' + digest(model_id)[:10]
        label = model_id.rsplit('/', 1)[-1]
        colors = ('#8b546f', '#63784c', '#927938', '#567c8c')
        color = colors[int(digest(model_id)[:4], 16) % len(colors)]
        order = 10
    return {'key': key, 'label': label, 'color': color, 'order': order}


def normalize_cells(matrix, model_id, cases, paired_groups, feature=FEATURE):
    """Keep all planned outcomes, including truncation without parsed response."""
    require(feature in FEATURE_INDEX, 'UNSUPPORTED_FEATURE')
    choices = FEATURE_INDEX[feature]['choices']
    selected = [row for row in matrix if row['model'] == model_id and row['variant'] == feature]
    require(len(selected) == 4, 'FOUR_CONDITIONS_REQUIRED')
    endpoints = defaultdict(dict)
    for group in paired_groups:
        if group.get('model') != model_id or group.get('variant') != feature or group.get('axis') != 'PROMPT':
            continue
        for pair in group['pairs']:
            for side in ('left', 'right'):
                row = pair[side]
                require(row is not None, 'PLANNED_PAIR_ENDPOINT_MISSING')
                condition = f"{row['prompt_condition']}/{row['reasoning']}"
                require(row['case'] not in endpoints[condition], 'DUPLICATE_CASE_IN_CONDITION')
                endpoints[condition][row['case']] = row
    cells = {}
    for row in selected:
        condition = f"{row['prompt_condition']}/{row['reasoning']}"
        require(condition in CONDITIONS and condition not in cells, 'INVALID_OR_DUPLICATE_CONDITION')
        counts = row['numeric_candidate_choices']
        require(not set(counts) - set(choices), 'UNSUPPORTED_ANSWER_CATEGORY')
        normalized = {choice: counts.get(choice, 0) for choice in choices}
        require(all(type(count) is int and count >= 0 for count in normalized.values()), 'INVALID_COUNT')
        total, collected = row['planned'], row['collected']
        require(type(total) is int and total > 0 and total == len(cases), 'COHORT_DENOMINATOR_MISMATCH')
        require(type(collected) is int and 0 <= collected <= total, 'INVALID_COLLECTED_COUNT')
        require(sum(normalized.values()) == total, 'CATEGORY_TOTAL_MISMATCH')
        require(sum(row['statuses'].values()) == total, 'STATUS_TOTAL_MISMATCH')
        require(set(endpoints[condition]) == set(cases), 'CONDITION_CASE_SET_MISMATCH')
        actual = Counter(entry['choice'] for entry in endpoints[condition].values())
        require(not set(actual) - set(choices), 'UNSUPPORTED_PAIR_CATEGORY')
        require(all(actual[choice] == normalized[choice] for choice in choices), 'PAIR_MATRIX_MISMATCH')
        require(set(row['response_ids']) == {entry['response_id'] for entry in endpoints[condition].values()}, 'RESPONSE_REFERENCE_MISMATCH')
        cells[condition] = {'total': total, 'collected': collected, 'counts': normalized,
                            'statuses': row['statuses'], 'parsed_response_absent': total - collected}
    return cells


def cohort_identity(dataset, source_run, input_hash, case_hash, candidate_hash):
    return digest([dataset, source_run, input_hash, case_hash, candidate_hash])


def latest_series(models):
    """Deduplicate exact configurations by saved timestamp, never by score."""
    grouped = defaultdict(list)
    for model in models:
        grouped[model['series_signature']].append(model)
    selected = []
    for items in grouped.values():
        ordered = sorted(items, key=lambda item: (datetime.fromisoformat(item['generated_at']), item['run']))
        latest = dict(ordered[-1])
        latest['previous_runs'] = [item['run'] for item in ordered[:-1]]
        selected.append(latest)
    duplicate_labels = Counter(model['key'] for model in selected)
    for model in selected:
        if duplicate_labels[model['key']] > 1:
            model['key'] += '-' + model['series_signature'][:8]
            model['label'] += ' · ' + model['protocol_label']
    return sorted(selected, key=lambda model: (model['order'], model['label'], model['run']))


def build_snapshot(root=ROOT, run_root=None):
    root = Path(root).resolve()
    run_root = Path(run_root).resolve() if run_root is not None else root / 'reports/experiments-run'
    preserved, inventory, records, provenance_cache = {}, [], [], {}

    def source_name(path):
        resolved = path.resolve()
        require(resolved.is_relative_to(root) or resolved.is_relative_to(run_root), 'SOURCE_OUTSIDE_BOUNDARY')
        return str(resolved.relative_to(root)) if resolved.is_relative_to(root) else str(resolved)

    def track(path):
        key = source_name(path)
        if key not in preserved:
            preserved[key] = sha(path)
        return preserved[key]

    def provenance(source_run, cases):
        path = root / source_run / 'results/00-input.json'
        if source_run not in provenance_cache:
            track(path)
            provenance_cache[source_run] = {row['id']: row.get('input', {}).get('provenance', {}).get('dataset', '')
                                           for row in json.loads(path.read_text())}
        index = provenance_cache[source_run]
        require(set(cases) <= set(index), 'SOURCE_CASES_NOT_FOUND')
        names = sorted({index[case] for case in cases})
        return dataset_family(names), names, str(path.relative_to(root))

    for run_dir in sorted(run_root.iterdir()) if run_root.is_dir() else []:
        require(run_dir.resolve().is_relative_to(run_root), 'RUN_OUTSIDE_BOUNDARY')
        config_path = run_dir / 'config.json'
        if not config_path.is_file():
            continue
        source_name(config_path)
        config = json.loads(config_path.read_text())
        evaluation = config.get('evaluation', config)
        dataset_config = evaluation.get('dataset', {})
        model_configs = evaluation.get('models', [])
        public = next((run_dir / p for p in ('00_input/public.jsonl', '01-input/public.jsonl') if (run_dir / p).is_file()), None)
        source = run_dir / '02_analysis/02_comparison/comparisons.json'
        entry = {'run': run_dir.name, 'source_run': dataset_config.get('source_run'),
                 'models': [model.get('model', model.get('key')) for model in model_configs],
                 'public_sha256': track(public) if public else None,
                 'status': 'NO_SAVED_A02', 'reason': 'comparisons.json is not saved'}
        inventory.append(entry)
        if not source.is_file():
            continue
        entry.update(status='CHECKING', reason=None)
        run_records = []
        try:
            require(public is not None, 'PUBLIC_INPUT_MISSING')
            private = run_dir / '00_input/private.jsonl'
            responses = run_dir / '02_analysis/01_results/responses.jsonl'
            for path in (config_path, source, public, private, responses):
                track(path)
            saved = json.loads(source.read_text())
            require(saved['response_rows_sha256'] == track(responses), 'STALE_A02_RESPONSE_HASH')
            private_rows = [json.loads(line) for line in private.read_text().splitlines() if line.strip()]
            feature_rows = {feature: [row for row in private_rows if row['variant'] == feature]
                            for feature in FEATURE_INDEX}
            require(all(feature_rows.values()), 'SEVEN_PRIVATE_FEATURES_REQUIRED')
            feature_cases = {feature: sorted(row['case'] for row in rows)
                             for feature, rows in feature_rows.items()}
            require(all(len(cases) == len(set(cases)) for cases in feature_cases.values()), 'DUPLICATE_PRIVATE_CASE')
            all_feature_rows = [row for rows in feature_rows.values() for row in rows]
            cases = sorted({row['case'] for row in all_feature_rows})
            public_ids = {json.loads(line)['item_id'] for line in public.read_text().splitlines() if line.strip()}
            require({row['item_id'] for row in all_feature_rows} <= public_ids, 'PUBLIC_FEATURE_ITEM_MISSING')
            source_runs = set()
            for row in all_feature_rows:
                match = re.search(r'reports/run/([^/]+)/', row.get('source', ''))
                require(match is not None, 'DATASET_SOURCE_UNCONFIRMED')
                source_runs.add('reports/run/' + match.group(1))
            require(len(source_runs) == 1, 'MIXED_SOURCE_RUNS')
            source_run = next(iter(source_runs))
            require(dataset_config.get('source_run') == source_run, 'DATASET_SOURCE_RUN_MISMATCH')
            dataset, source_names, provenance_path = provenance(source_run, cases)
            contract = {name: track(run_dir / '01_evaluation/02_request' / name) for name in CONTRACT_FILES}
            protocol_hash = digest(contract)
            case_hash = digest(feature_cases)
            feature_info = {feature: {'case_count': len(feature_cases[feature]),
                            'case_ids_sha256': digest(feature_cases[feature]),
                            'candidate_sha256': digest(sorted([{key: row.get(key) for key in
                            ('case', 'item_id', 'reference', 'alternative_answer')} for row in rows],
                            key=lambda row: row['case']))} for feature, rows in feature_rows.items()}
            candidate_hash = digest({feature: info['candidate_sha256'] for feature, info in feature_info.items()})
            group_key = cohort_identity(dataset, source_run, track(public), case_hash, candidate_hash)
            model_index = {model['key']: model for model in model_configs}
            actual_models = sorted({row['model'] for row in saved['matrix'] if row['variant'] in FEATURE_INDEX})
            require(bool(actual_models), 'FEATURE_MATRIX_MISSING')
            for model_id in actual_models:
                require(model_id in model_index, 'MODEL_CONFIG_NOT_FOUND')
                model_config = model_index[model_id]
                actual_id = model_config['model']
                features = {feature: {'cells': normalize_cells(saved['matrix'], model_id,
                            feature_cases[feature], saved['paired_groups'], feature)} for feature in FEATURE_INDEX}
                settings = {key: value for key, value in model_config.items()
                            if key in ('transport', 'reasoning_efforts', 'output_limits', 'max_output_tokens', 'thinking_budget', 'thinking', 'extra_body')}
                model = {**model_style(actual_id), 'id': model_id, 'model_id': actual_id, 'run': run_dir.name,
                         'evaluation_source': saved.get('evaluation_source', run_dir.name),
                         'features': features, 'generated_at': saved['generated_at'], 'settings': settings,
                         'source': {'path': source_name(source), 'sha256': track(source)},
                         'protocol_sha256': protocol_hash, 'contract': contract,
                         'series_signature': digest([actual_id, protocol_hash, settings])}
                run_records.append({'dataset': dataset, 'cohort_key': group_key,
                                    'source_run': source_run, 'source_provenance': source_names,
                                    'provenance_path': provenance_path, 'input_sha256': track(public),
                                    'case_ids_sha256': case_hash, 'candidate_sha256': candidate_hash,
                                    'case_count': len(cases), 'features': feature_info, 'model': model})
            records.extend(run_records)
            entry.update(status='INCLUDED', dataset=dataset, source_run=source_run,
                         cohort_key=group_key, case_count=len(cases))
        except (ValueError, KeyError, OSError, TypeError) as error:
            entry.update(status='NOT_COMPARABLE', reason=str(error))
    require(bool(records), 'NO_COMPARABLE_SAVED_RESULTS')
    protocol_times = {}
    for record in records:
        model = record['model']
        key = model['protocol_sha256']
        when = datetime.fromisoformat(model['generated_at'])
        protocol_times[key] = min(when, protocol_times.get(key, when))
    protocol_labels = {key: f'v{index + 1}' for index, key in enumerate(sorted(protocol_times, key=protocol_times.get))}
    datasets = []
    for dataset_name in sorted({record['dataset'] for record in records}, key=lambda name: (name != 'TAT-QA', name)):
        grouped = defaultdict(list)
        for record in records:
            if record['dataset'] == dataset_name:
                grouped[record['cohort_key']].append(record)
        cohorts = []
        for group_key, items in grouped.items():
            cohort = {key: value for key, value in items[0].items() if key not in ('model', 'dataset', 'cohort_key')}
            cohort['key'] = group_key
            models = [item['model'] for item in items]
            for model in models:
                model['protocol_label'] = protocol_labels[model['protocol_sha256']]
            cohort['models'] = latest_series(models)
            included_ids = {model['model_id'] for model in cohort['models']}
            pending = []
            for entry in inventory:
                if entry['status'] == 'INCLUDED' or entry['source_run'] != cohort['source_run'] or entry['public_sha256'] != cohort['input_sha256']:
                    continue
                for model_id in entry['models']:
                    if model_id not in included_ids:
                        pending.append({'model_id': model_id, **model_style(model_id),
                                        'run': entry['run'], 'status': entry['status'], 'reason': entry['reason']})
            cohort['pending_models'] = pending
            cohort['protocols_equal'] = len({model['protocol_sha256'] for model in cohort['models']}) == 1
            cohorts.append(cohort)
        cohorts.sort(key=lambda cohort: (-cohort['case_count'], cohort['key']))
        datasets.append({'key': re.sub('[^a-z0-9]+', '-', dataset_name.lower()).strip('-'),
                         'label': dataset_name, 'cohorts': cohorts})
    return {'schema_version': 3, 'features': FEATURES, 'generated_at': datetime.now(timezone.utc).isoformat(),
            'datasets': datasets, 'inventory_summary': dict(Counter(entry['status'] for entry in inventory))}, preserved, inventory


def render_fragment(snapshot):
    """Render the saved-data snapshot without writing artifacts or calling models."""
    payload = json.dumps(snapshot, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    fragment = (TEMPLATES / 'ic-value-quadrant.fragment.html').read_text().replace('__SNAPSHOT_JSON__', payload)
    require('__SNAPSHOT_JSON__' not in fragment and len(fragment.encode()) < 1_000_000, 'INVALID_INLINE_FRAGMENT')
    return fragment


def render_page(snapshot, viewer=False):
    fragment = render_fragment(snapshot)
    layout = 'html{background:#fffdf9}body{margin:0;padding:0}' if viewer else 'html{background:#eee8df}body{margin:0;padding:12px}@media(max-width:620px){body{padding:6px}}'
    return '<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width,initial-scale=1">\n<meta name="color-scheme" content="light">\n<title>7조건 사분면 · 두 화면 비교</title>\n<style>' + layout + '</style>\n</head>\n<body>\n' + fragment + '\n</body>\n</html>\n'


def main():
    for directory in (OUT, LOG, INLINE.parent):
        directory.mkdir(parents=True, exist_ok=True)
    snapshot, preserved, inventory = build_snapshot()
    require(all(sha(ROOT / path) == value for path, value in preserved.items()), 'SOURCE_CHANGED_DURING_BUILD')
    fragment = render_fragment(snapshot)
    INLINE.write_text(fragment)
    page = render_page(snapshot)
    (OUT / 'ic-value-quadrant.html').write_text(page)
    write_json(OUT / 'source-snapshot.json', snapshot)
    write_json(OUT / 'run-inventory.json', inventory)
    verification = {'status': 'PASS', 'generated_at': snapshot['generated_at'], 'revision': 'model-checkbox-quadrant-symbols',
                    'feature_count': len(FEATURES), 'screen_count': 2,
                    'model_calls': 0, 'dataset_count': len(snapshot['datasets']),
                    'cohort_count': sum(len(dataset['cohorts']) for dataset in snapshot['datasets']),
                    'run_inventory': snapshot['inventory_summary'], 'source_files_preserved': True,
                    'sources': preserved, 'html_sha256': sha(OUT / 'ic-value-quadrant.html'),
                    'browser_visual_validation': 'PENDING'}
    write_json(LOG / 'build-verification.json', verification)
    with (LOG / 'events.jsonl').open('a') as stream:
        stream.write(json.dumps({'at': snapshot['generated_at'], 'event': 'MODEL_QUADRANT_SYMBOL_LEGEND_CREATED',
                                'source_files': len(preserved), 'model_calls': 0,
                                'dataset_count': len(snapshot['datasets'])}, ensure_ascii=False) + '\n')
    print(json.dumps({'html': str(OUT / 'ic-value-quadrant.html'), 'inline': str(INLINE),
                      'datasets': [{'name': dataset['label'], 'cohorts': [{'questions': cohort['case_count'],
                                    'models': [model['label'] for model in cohort['models']],
                                    'pending': [model['label'] for model in cohort['pending_models']]}
                                   for cohort in dataset['cohorts']]} for dataset in snapshot['datasets']],
                      'inventory': snapshot['inventory_summary'], 'source_files_preserved': True}, ensure_ascii=False))


if __name__ == '__main__':
    main()
