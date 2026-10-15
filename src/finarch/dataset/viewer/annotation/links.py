"""Resolve per-variant G02 links against saved annotation evidence."""
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlencode

from .sources import catalogs, read_optional, match_edit


def round_paths(bundle):
    generation = bundle / '02-generation'
    if bundle.is_symlink() or generation.is_symlink() or not generation.is_dir():
        return []
    return sorted((path for path in generation.iterdir() if path.is_dir() and not path.is_symlink()
                   and re.fullmatch(r'\d+-round', path.name)), reverse=True)


def stage_path(round_path, case, variant):
    path = round_path / case / variant / '02-generate-text'
    return path if path.resolve().is_relative_to(round_path.resolve()) else None


def patch_pairs(patches):
    if not isinstance(patches, list) or not patches or any(
        not isinstance(patch, dict) or not isinstance(patch.get('text'), str)
        or not isinstance(patch.get('before'), str) for patch in patches
    ):
        return set()
    return {(separator.join(patch['text'] for patch in patches),
             separator.join(patch['before'] for patch in patches)) for separator in ('', ' || ')}


def combined_source_edit(stage, variant):
    # Legacy source exports include both the value insertion and its attribution.
    # Compose only verified insertions using their saved positions and contexts.
    input_data = read_optional(stage / '01-input.json')
    comparison = read_optional(stage.parent / '03-validation/04-comparison.json')
    patches = read_optional(stage / '05-patches.json')
    base = comparison.get('value_dependency') if isinstance(comparison, dict) else None
    if not base:
        base_variant = '01-ic-value-before' if variant == '03-ic-source-type-1' else '02-ic-value-after'
        round_path, case = stage.parents[2], stage.parents[1].name
        for candidate in round_paths(round_path.parent.parent):
            if candidate.name > round_path.name:
                continue
            base_stage = stage_path(candidate, case, base_variant)
            base = read_optional(base_stage / '05-patches.json') if base_stage else None
            if base:
                break
    if not patch_pairs(base) or not patch_pairs(patches) or len(base) != 1 or len(patches) != 1:
        return None
    value, source = base[0], patches[0]
    if value['before'] or source['before'] or not isinstance(input_data, dict):
        return None
    context = input_data.get('context')
    if not isinstance(context, str):
        return None
    for patch in (value, source):
        if type(patch.get('start')) is not int or patch.get('end') != patch['start']:
            return None
        if not 0 <= patch['start'] <= len(context):
            return None
    if context[value['start']:value['start'] + len(value['text'])] != value['text']:
        return None
    observation = read_optional(stage / '04-observation.json')
    composed = context[:source['start']] + source['text'] + context[source['start']:]
    if not isinstance(observation, dict) or observation.get('context') != composed:
        return None
    offset = source['start'] - value['start']
    if 0 <= offset <= len(value['text']):
        inserted = value['text'][:offset] + source['text'] + value['text'][offset:]
    elif offset < 0:
        inserted = source['text'] + ' || ' + value['text']
    else:
        inserted = value['text'] + ' || ' + source['text']
    return inserted, ''


def target(root, run, round_name, item, row, stage, method, requested_round=None):
    observation = read_optional(stage / '04-observation.json')
    if not isinstance(observation, dict) or not isinstance(observation.get('context'), str):
        return None
    if not (root / run / '01-preparation' / item['case']).is_dir():
        return None
    context_key = hashlib.sha256(json.dumps({key: observation.get(key) for key in ('context', 'question')},
                                           sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    query = {'run': run, 'round': requested_round or round_name, 'case': item['case'],
             'variant': row['variant'], 'stage': '02-generate-text'}
    return {'status': 'AVAILABLE', 'href': '/?' + urlencode(query) + '#g02-full-context', **query, 'origin_round': round_name,
            'path': str((stage / '04-observation.json').relative_to(root.parent.parent)),
            'match_path': str((stage / '05-patches.json').relative_to(root.parent.parent)),
            'context_sha256': context_key, 'method': method}


def case_links(groups, runs_root, group_id, case_name):
    root = Path(runs_root)
    group = next((group for group in groups if group['id'] == group_id), None)
    item = next((item for item in group['cases'] if item['case'] == case_name), None) if group else None
    if item is None:
        raise ValueError('Unknown annotation group or case.')
    if not re.fullmatch(r'test-\d+', case_name):
        raise ValueError('Invalid annotation case.')
    candidates = []
    if group.get('run') and re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]*', group['run']):
        rounds = round_paths(root / group['run'])
        requested_round = group.get('round')
        preparation = root / group['run'] / '01-preparation' / case_name / str(requested_round)
        if requested_round in {path.name for path in rounds} or (
            isinstance(requested_round, str) and re.fullmatch(r'\d+-round', requested_round)
            and preparation.is_dir() and not preparation.is_symlink()
        ):
            candidates = [{'run': group['run'], 'rounds': rounds}]
    elif not group.get('run') and item.get('source_reference'):
        reference = item['source_reference']
        for catalog in catalogs(root):
            metadata = catalog['index'].get(case_name)
            if metadata and all(metadata.get(key) == reference.get(key) for key in ('type', 'source_id', 'dataset')):
                if match_edit(item, catalog):
                    candidates.append(catalog)
    result = {}
    for row in item['rows']:
        missing = {'status': 'UNAVAILABLE', 'reason': '평가 JSON과 일치하는 G02 저장 기록을 확인할 수 없습니다.'}
        result[row['variant']] = missing
        if not re.fullmatch(r'0[1-7]-[a-z0-9-]+', row['variant']):
            continue
        edits = {(entry['inserted'], entry['removed']) for entry in row['content']}
        if len(edits) > 1:
            missing['reason'] = '평가자별 본문이 달라 G02를 하나로 정할 수 없습니다.'
            continue
        matches = []
        for candidate in candidates:
            for round_path in candidate['rounds']:
                requested_round = group.get('round')
                if group.get('run') and (not isinstance(requested_round, str)
                                        or not re.fullmatch(r'\d+-round', requested_round)
                                        or round_path.name > requested_round):
                    continue
                stage = stage_path(round_path, case_name, row['variant'])
                if stage is None or not stage.parent.is_dir():
                    continue
                method = 'EXPLICIT_RUN_ROUND'
                if not group.get('run'):
                    if not edits or edits == {('', '')}:
                        continue
                    saved = patch_pairs(read_optional(stage / '05-patches.json'))
                    method = 'EXACT_SAVED_EDIT'
                    if not edits.issubset(saved) and row['variant'] in ('03-ic-source-type-1', '04-ic-source-type-2'):
                        combined = combined_source_edit(stage, row['variant'])
                        if combined:
                            saved.add(combined)
                            method = 'EXACT_COMBINED_INSERTIONS'
                    if not edits.issubset(saved):
                        continue
                link = target(root, candidate['run'], round_path.name, item, row, stage, method,
                              requested_round if group.get('run') else None)
                if link:
                    matches.append(link)
                if group.get('run'):
                    break  # The dataset viewer carries the latest variant at or before the requested round.
        if matches and len({link['context_sha256'] for link in matches}) == 1:
            result[row['variant']] = matches[0]
        elif matches:
            missing['reason'] = '같은 변경 문장에 서로 다른 전체 본문이 저장되어 있습니다.'
    return {'group': group_id, 'case': case_name, 'links': result}
