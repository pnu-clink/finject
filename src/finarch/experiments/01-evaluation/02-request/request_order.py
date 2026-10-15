"""Order requests and recover their item identities from model manifests."""
from collections import Counter
import json
from pathlib import Path

run_layout = __import__('finarch.experiments.90-operations.run_layout', fromlist=['*'])

IDENTITY_FIELDS = ('item_id', 'case', 'experiment', 'variant')


def summarize_items(items):
    """E02.03: Count unique items, never repeated model/prompt/reasoning rows."""
    identities, pairs = {}, {}
    for row in items:
        item = {key: row.get(key) for key in IDENTITY_FIELDS}
        if (any(not isinstance(item[key], str) or not item[key]
                for key in ('item_id', 'case', 'variant'))
                or type(item['experiment']) is not int or item['experiment'] not in (1, 2)
                or (item['variant'] == 'ORIGINAL') != (item['experiment'] == 1)):
            raise ValueError('INVALID_MANIFEST_ITEM_IDENTITY')
        item_id, pair = item['item_id'], (item['case'], item['variant'])
        if item_id in identities and identities[item_id] != item:
            raise ValueError('MANIFEST_ITEM_IDENTITY_CONFLICT:' + item_id)
        if pair in pairs and pairs[pair] != item_id:
            raise ValueError('MANIFEST_CASE_VARIANT_ID_CONFLICT:' + '/'.join(pair))
        identities[item_id], pairs[pair] = item, item_id
    unique = list(identities.values())
    return {'items': unique, 'case_ids': list(dict.fromkeys(item['case'] for item in unique)),
            'originals': sum(item['experiment'] == 1 for item in unique),
            'variants': sum(item['experiment'] == 2 for item in unique),
            'variant_counts': dict(Counter(item['variant'] for item in unique if item['experiment'] == 2))}


def selection_from_manifests(root, *, public=None, require_same_items=False):
    """E02.03: Read the sole saved execution identities, including legacy runs."""
    root = Path(root)
    config = run_layout.evaluation_config(root)
    all_items, files, inputs, first_ids = [], [], {}, None
    expected = None if public is None else {
        row['item_id']: {key: value for key, value in row.items() if key != 'item_id'} for row in public}
    for model in config['models']:
        relative = run_layout.requests(root, model['key']).relative_to(root)
        target = (root / relative).resolve()
        if not target.is_relative_to(root.resolve()):
            raise ValueError('MANIFEST_PATH_OUTSIDE_RUN')
        if not target.is_file():
            raise ValueError('REQUEST_MANIFEST_REQUIRED:' + str(relative))
        model_items, trial_ids = [], set()
        with target.open() as stream:
            for line in stream:
                if not line.strip():
                    continue
                request = json.loads(line)
                trial_id = request.get('trial_id')
                if not isinstance(trial_id, str) or not trial_id or trial_id in trial_ids:
                    raise ValueError('DUPLICATE_OR_MISSING_MANIFEST_TRIAL_ID')
                trial_ids.add(trial_id)
                item_id = request['item_id']
                payload = request['input']
                if item_id in inputs and inputs[item_id] != payload:
                    raise ValueError('MANIFEST_ITEM_INPUT_CONFLICT:' + item_id)
                if expected is not None and (item_id not in expected or expected[item_id] != payload):
                    raise ValueError('PUBLIC_MANIFEST_INPUT_MISMATCH:' + item_id)
                inputs[item_id] = payload
                model_items.append({key: request.get(key) for key in IDENTITY_FIELDS})
        if not model_items:
            raise ValueError('REQUEST_MANIFEST_EMPTY:' + str(relative))
        model_items = summarize_items(model_items)['items']
        ids = {item['item_id'] for item in model_items}
        if require_same_items and first_ids is not None and ids != first_ids:
            raise ValueError('MODEL_MANIFEST_COHORT_MISMATCH')
        first_ids = ids if first_ids is None else first_ids
        files.append(relative.as_posix())
        all_items.extend(model_items)
    if not files:
        raise ValueError('MODEL_REQUEST_MANIFESTS_REQUIRED')
    summary = summarize_items(all_items)
    if expected is not None:
        by_id = {item['item_id']: item for item in summary['items']}
        if set(by_id) != set(expected):
            raise ValueError('PUBLIC_MANIFEST_ID_MISMATCH')
        summary = summarize_items([by_id[row['item_id']] for row in public])
    return {**summary, 'manifest_files': files}


def prioritize_pilot(trials, case_ids):
    """EX02.1p: Put all conditions for the selected cases before the remainder."""
    if case_ids is None:
        return trials
    if (not isinstance(case_ids, list) or not case_ids
            or any(not isinstance(case, str) or not case for case in case_ids)
            or len(case_ids) != len(set(case_ids))):
        raise ValueError('PILOT_CASES_MUST_BE_UNIQUE_NONEMPTY_STRINGS')
    requested = set(case_ids)
    available = {trial['case'] for trial in trials}
    if not requested <= available:
        raise ValueError('PILOT_CASE_NOT_IN_FROZEN_COHORT')
    return sorted(trials, key=lambda trial: (trial['case'] not in requested, trial['experiment']))
