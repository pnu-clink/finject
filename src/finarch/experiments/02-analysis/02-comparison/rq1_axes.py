"""RQ1 axes from saved scores and explicitly confirmed references, never labels alone."""
from decimal import Decimal, InvalidOperation

store = __import__('finarch.experiments.90-operations.storage', fromlist=['*'])


def confirmed_reference(item, public, contract):
    """Return a qualified frozen reference, or explicit gaps; do not infer answerability."""
    record = (contract or {}).get('items', {}).get(item['item_id'])
    if not record:
        return None, ['REFERENCE_CRITERIA_NOT_ESTABLISHED']
    if record.get('status') != 'CONFIRMED' or not record.get('source'):
        return None, ['REFERENCE_CRITERIA_NOT_ESTABLISHED']
    if record.get('input_sha256') != store.digest(public):
        raise ValueError('RQ1_REFERENCE_INPUT_CHANGED:' + item['item_id'])
    if record.get('answerability') not in ('ANSWERABLE', 'UNANSWERABLE'):
        raise ValueError('RQ1_REFERENCE_ANSWERABILITY_REQUIRED:' + item['item_id'])
    gaps = []
    if record['answerability'] == 'ANSWERABLE':
        # A contract qualifies an existing reference; it cannot replace frozen gold.
        if record.get('reference') != item.get('reference'):
            raise ValueError('RQ1_REFERENCE_MUST_PRESERVE_FROZEN_GOLD:' + item['item_id'])
        if record.get('unit_policy') != 'EXPLICIT_RESPONSE_SCALE' or record.get('expected_scale') not in ('raw', 'percent', 'thousand', 'million', 'billion'):
            gaps.append('UNIT_CRITERION_NOT_CONFIRMED')
        if record.get('precision_policy') != 'EXACT_FROZEN_DECIMAL' or not isinstance(record.get('reference', {}).get('reference_precision'), int):
            gaps.append('PRECISION_CRITERION_NOT_CONFIRMED')
    return record, gaps


def numeric_correctness(response, reference):
    """Check a valid numeric decision in a confirmed question scale; no rescaling."""
    if response.get('answer') is None:
        return False
    if response.get('answer_meta', {}).get('scale') != reference['expected_scale']:
        return False
    try:
        answer = Decimal(str(response['answer']))
        gold = Decimal(str(reference['reference']['reference_answer']))
        if not answer.is_finite() or not gold.is_finite():
            return None
        return answer == gold
    except (InvalidOperation, ValueError, KeyError):
        return None


def strict_axes(original, variant, original_reference, variant_reference, assessment):
    """Separate reference-based decisions from the judge's saved adaptation_success."""
    x, y, category = None, None, 'ANSWERABILITY_NOT_ESTABLISHED'
    if original and original.get('status') == 'VALID' and original_reference and original_reference['answerability'] == 'ANSWERABLE':
        x = numeric_correctness(original.get('response') or {}, original_reference)
    if not variant or variant.get('status') != 'VALID' or not variant_reference:
        return x, y, category
    response = variant.get('response') or {}
    is_null = response.get('answer') is None
    if variant_reference['answerability'] == 'ANSWERABLE':
        if is_null:
            y, category = False, 'OVER_ABSTENTION'
        else:
            number_match = numeric_correctness(response, variant_reference)
            if number_match is False:
                y, category = False, 'INCORRECT_ANSWER'
            elif number_match is True and assessment and assessment.get('review_status') == 'COMPLETED':
                y = assessment.get('adaptation_success')
                category = 'CORRECT_ANSWER' if y is True else 'UNSUPPORTED_ANSWER' if y is False else 'ANSWER_UNDETERMINED'
    elif not is_null:
        y, category = False, 'INAPPROPRIATE_NUMERIC_ANSWER'
    elif assessment and assessment.get('review_status') == 'COMPLETED':
        y = assessment.get('adaptation_success')
        category = 'SUPPORTED_ABSTENTION' if y is True else 'UNSUPPORTED_ABSTENTION' if y is False else 'ABSTENTION_UNDETERMINED'
    return x, y, category


def quadrant(x, y):
    if type(x) is not bool or type(y) is not bool:
        return None
    return 1 if x and y else 2 if y else 4 if x else 3


def placement(x, y, original_status, variant_status, assessment_status, gaps=()):
    if original_status != 'VALID':
        return 'ORIGINAL_UNAVAILABLE'
    if x is None:
        return 'ORIGINAL_CRITERIA_UNCONFIRMED' if gaps else 'ORIGINAL_UNASSESSED'
    if variant_status != 'VALID':
        return 'VARIANT_UNAVAILABLE'
    if y is not None:
        return 'PLACED'
    if gaps:
        return 'VARIANT_CRITERIA_UNCONFIRMED'
    return {'NOT_REVIEWED': 'JUDGE_NOT_REVIEWED', 'REVIEW_FAILED': 'JUDGE_REVIEW_FAILED',
            'NOT_REVIEWABLE': 'JUDGE_NOT_REVIEWABLE', 'SOURCE_MISSING': 'JUDGE_SOURCE_MISSING'}.get(assessment_status, 'SEMANTIC_UNDETERMINED')


def aggregate(pairs, screen=False):
    """Use fixed planned pairs, and leave failure F and unresolved U outside quadrants."""
    prefix = 'screen_' if screen else ''
    x_key = prefix + 'original_correctness'
    q_key = prefix + 'quadrant'
    status_key = prefix + 'placement_status'
    planned = len(pairs)
    counts = {str(q): sum(p[q_key] == q for p in pairs) for q in range(1, 5)}
    placed = sum(counts.values())
    statuses = {}
    for p in pairs:
        statuses[p[status_key]] = statuses.get(p[status_key], 0) + 1
    groups = []
    for x, title in ((True, 'YES'), (False, 'NO'), (None, 'UNASSESSED')):
        rows = [p for p in pairs if p[x_key] is x]
        successes = sum(p[q_key] in (1, 2) for p in rows)
        failures = sum(p[q_key] in (3, 4) for p in rows)
        unavailable = sum(p['variant_status'] != 'VALID' for p in rows)
        unresolved = len(rows) - successes - failures - unavailable
        denominator = len(rows)
        groups.append({'original_group': title, 'planned_pairs': denominator,
            'success': successes, 'inappropriate': failures, 'F': unavailable, 'U': unresolved,
            'confirmed_success_rate': successes / denominator if denominator and x is not None else None,
            'success_range': [successes / denominator, (successes + unresolved) / denominator] if denominator and x is not None else None,
            'provisional': bool(unresolved)})
    return {'planned_pairs': planned,
        'original_cases': len({(p['source_type'], p['original_item_id']) for p in pairs}),
        'original_condition_groups': len({(p['model'], p['original_item_id'], p['prompt_condition'], p['reasoning']) for p in pairs}),
        'quadrants': {q: {'count': n, 'ratio_of_planned': n / planned if planned else None} for q, n in counts.items()},
        'placed_pairs': placed, 'unplaced_pairs': planned - placed,
        'placement_rate': placed / planned if planned else None, 'placement_counts': statuses,
        'original_groups': groups,
        'pair_succ': counts['1'] / planned if planned else None,
        'boundary': 'SAVED_NUMERIC_SCREEN_AND_LLM_REVIEW_NOT_FINAL_RQ1' if screen else 'CONFIRMED_REFERENCE_CRITERIA_REQUIRED'}
