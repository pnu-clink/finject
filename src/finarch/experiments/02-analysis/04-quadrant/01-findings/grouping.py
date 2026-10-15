"""Trace F records to conditions and validate model-created topic groups."""
from collections import Counter, defaultdict

CONDITIONS = ('unguided/off', 'unguided/on', 'guided/off', 'guided/on')


def unique(rows, key):
    index = {row[key]: row for row in rows}
    if len(index) != len(rows):
        raise ValueError('A04_DUPLICATE_' + key.upper())
    return index


def trace(findings, observations, responses):
    """Observations supply provenance; only F records enter the model request."""
    unique(findings, 'id')
    observation_index = unique(observations, 'id')
    response_index = unique(responses, 'response_id')
    linked = []
    for finding in findings:
        if not finding['id'].startswith('F'):
            raise ValueError('A04_FINDINGS_ONLY')
        refs = set()
        for observation_id in finding['interpretation_ids']:
            if observation_id not in observation_index:
                raise ValueError('A04_UNKNOWN_OBSERVATION:' + observation_id)
            refs.update(observation_index[observation_id]['response_ids'])
        by_condition = defaultdict(list)
        for response_id in sorted(refs):
            if response_id not in response_index:
                raise ValueError('A04_UNKNOWN_RESPONSE:' + response_id)
            row = response_index[response_id]
            prompt = {'P0': 'unguided', 'P1': 'guided'}.get(row['prompt_condition'], row['prompt_condition'])
            condition = prompt + '/' + row['reasoning']
            if condition not in CONDITIONS:
                raise ValueError('A04_UNSUPPORTED_CONDITION:' + condition)
            by_condition[condition].append({'response_id': response_id, 'case': row['case'],
                'variant': row['variant'], 'model': row['model']})
        linked.append({'finding': finding,
            'condition_scope': 'MULTI_CONDITION' if len(by_condition) > 1 else 'SINGLE_CONDITION' if by_condition else 'NO_RESPONSE_REFERENCES',
            'conditions': {k: by_condition[k] for k in CONDITIONS if k in by_condition}})
    return linked


def model_input(linked):
    fields = ('id', 'title', 'claim', 'alternatives', 'limitation', 'decision')
    return [{**{k: row['finding'][k] for k in fields}, 'cited_conditions': list(row['conditions'])} for row in linked]


def validate(value, request):
    """Require exact F coverage and verbatim citations, without changing claims."""
    if value['run'] != request['input']['run']:
        raise ValueError('A04_RUN_MISMATCH')
    findings = unique(request['input']['findings'], 'id')
    seen, group_ids = [], set()
    for group in value['groups']:
        if group['id'] in group_ids:
            raise ValueError('A04_DUPLICATE_GROUP')
        group_ids.add(group['id'])
        members = group['finding_ids']
        if not members or len(members) != len(set(members)) or set(members) - set(findings):
            raise ValueError('A04_INVALID_GROUP_MEMBERS')
        seen.extend(members)
        profiles = group['condition_profiles']
        if len(profiles) != 4 or {p['condition'] for p in profiles} != set(CONDITIONS):
            raise ValueError('A04_FOUR_CONDITIONS_REQUIRED')
        for profile in profiles:
            eligible = {f for f in members if profile['condition'] in findings[f]['cited_conditions']}
            if len(profile['finding_ids']) != len(set(profile['finding_ids'])) or set(profile['finding_ids']) != eligible:
                raise ValueError('A04_CONDITION_COVERAGE_MISMATCH')
            if not eligible and profile['citations']:
                raise ValueError('A04_CITATION_WITHOUT_CONDITION_EVIDENCE')
            if eligible and not profile['citations']:
                raise ValueError('A04_PROFILE_CITATIONS_REQUIRED')
            for citation in profile['citations']:
                if citation['finding_id'] not in eligible:
                    raise ValueError('A04_CITATION_OUTSIDE_CONDITION')
                source = findings[citation['finding_id']][citation['field']]
                if not citation['quote'].strip() or citation['quote'] not in source:
                    raise ValueError('A04_QUOTE_NOT_IN_FINDING')
    if len(seen) != len(set(seen)) or set(seen) != set(findings):
        raise ValueError('A04_EXACT_FINDING_COVERAGE_REQUIRED')
    return True


def collect(value, linked):
    membership = {ref: group['id'] for group in value['groups'] for ref in group['finding_ids']}
    linked = [{**f, 'group_id': membership[f['finding']['id']]} for f in linked]
    cells = []
    for condition in CONDITIONS:
        members = [f for f in linked if condition in f['conditions']]
        refs = {r['response_id']: r for f in members for r in f['conditions'][condition]}
        cells.append({'condition': condition, 'finding_ids': [f['finding']['id'] for f in members],
            'finding_count': len(members), 'shared_finding_count': sum(f['condition_scope'] == 'MULTI_CONDITION' for f in members),
            'cited_response_count': len(refs), 'cited_case_count': len({r['case'] for r in refs.values()})})
    return {'schema_version': 1, 'run': value['run'], 'scope': 'A03_FINDINGS_ONLY',
        'groups': value['groups'], 'findings': linked, 'cells': cells,
        'meaning': 'Every F retains its claim, alternatives, limitation and decision. Condition membership traces cited responses; it is not an isolated effect or a success rate. Multi-condition findings appear in multiple cells.',
        'counts': {'findings': len(linked), 'groups': len(value['groups']),
            'shared_findings': sum(f['condition_scope'] == 'MULTI_CONDITION' for f in linked),
            'unlinked_findings': sum(not f['conditions'] for f in linked),
            'condition_mentions': sum(c['finding_count'] for c in cells),
            'decisions': dict(Counter(f['finding']['decision'] for f in linked))}}
