"""Bounded, observation-only recovery witnesses for reviewed source grammars."""
from decimal import Decimal
import hashlib
import json
import re

from finarch.dataset.shared.calculation.number_normalization import load_rules, normalize_number

VERSION = 'BOUNDED_PYTHON_V1'
RULES = ('current_tax_subtotal', 'closed_three_asset_weights')
LIMITS = {'components': 8, 'relations': 16, 'steps': 2}
NUM = r'(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?'
FIELDS = ('target_id', 'kind', 'item', 'entity', 'period', 'unit')
TAX = re.compile(
    r'^[ \t]*\|[ \t]*(?P<year1>\d{4})[ \t]*\|[ \t]*(?P<year2>\d{4})[ \t]*\n'
    r'Current:[ \t]*Federal[ \t]*\|(?P<f1>[^|\n]*)\|(?P<f2>[^|\n]*)\n'
    r'Current:[ \t]*State[ \t]*\|(?P<s1>[^|\n]*)\|(?P<s2>[^|\n]*)\n'
    r'[ \t]*\|(?P<t1>[^|\n]*)\|(?P<t2>[^|\n]*)\n'
    r'(?=Deferred:[ \t]*Federal[ \t]*\|)', re.MULTILINE)
NAME = r'[A-Za-z][A-Za-z0-9 -]{0,40}?'
CLOSED = re.compile(
    r'(?:An\s+investor|(?P<manager>' + NAME + r'))\s+is\s+managing\s+a\s+diversified\s+portfolio\s+'
    r'consisting\s+of\s+(?:three|3)\s+different\s+assets:\s*'
    r'(?P<a>' + NAME + r'),\s*(?P<b>' + NAME + r'),\s*and\s+(?P<c>' + NAME + r')\.')
ALLOCATION = re.compile(r'(?P<actor>The\s+investor|[A-Z][A-Za-z0-9 -]{0,40}?)\s+has\s+allocated\s+their\s+portfolio\s+[^.]+\.')


def tax_intro(context, match):
    pattern = (r"(?:The|(?P<company>[A-Z][A-Za-z0-9 .&-]{0,60}?)'s)\s+components\s+of\s+income\s+tax\s+"
               r'expense\s+from\s+operations\s+for\s+fiscal\s+' + match['year1'] +
               r'\s+and\s+fiscal\s+' + match['year2'] + r'\s+consisted\s+of\s+the\s+following:')
    matches = list(re.finditer(pattern, context))
    if len(matches) != 1:
        raise ValueError('TAX_RELATION_UNCONFIRMED')
    return matches[0]


def portfolio_parts(context):
    matches = list(CLOSED.finditer(context))
    if len(matches) != 1:
        raise ValueError('CLOSED_PORTFOLIO_NOT_CONFIRMED')
    closed = matches[0]
    names = [closed[k].strip() for k in ('a', 'b', 'c')]
    if len(set(names)) != 3:
        raise ValueError('DUPLICATE_ASSET_NAMES')
    weight = re.compile(r'(?P<amount>' + NUM + r')%\s+(?:(?:is\s+)?invested\s+)?in\s+(?P<asset>' +
                        '|'.join(re.escape(name) for name in sorted(names, key=len, reverse=True)) + r')(?=\s|[,\.]|$)')
    return closed, names, weight


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def descriptor(context, fact_span, target_id):
    """Read only source location and labels; never copy a target amount or quote."""
    result = dict(target_id=target_id, kind='unsupported', item='', entity='', period='', unit='')
    for match in TAX.finditer(context):
        for col in (1, 2):
            for key, label in (('s', 'State'), ('f', 'Federal')):
                start, end = match.span(f'{key}{col}')
                if start <= fact_span[0] < fact_span[1] <= end:
                    try:
                        intro = tax_intro(context, match)
                    except ValueError:
                        return result
                    return dict(result, kind='current_tax', item=label, entity=intro['company'] or 'company',
                                period=match[f'year{col}'], unit='USD')
    try:
        _, _, weight_pattern = portfolio_parts(context)
    except ValueError:
        return result
    for allocation in ALLOCATION.finditer(context):
        for weight in weight_pattern.finditer(allocation[0]):
            start, end = weight.span('amount')
            start += allocation.start(); end += allocation.start() + 1
            if start <= fact_span[0] < fact_span[1] <= end:
                return dict(result, kind='portfolio_weight', item=weight['asset'],
                            entity='portfolio', period='allocation', unit='%')
    return result


def screen_recovery(observation, target_descriptor, policy):
    """No graph, gold, hidden value, or original context is accepted as evidence."""
    observed = {key: observation[key] for key in ('context', 'question')}
    target = {key: target_descriptor.get(key, '') for key in FIELDS}
    rules, number_hash = load_rules()
    effective = {'enabled': bool(policy and policy.get('enabled') is True),
                 'rules': list((policy or {}).get('rules', RULES)), 'limits': LIMITS,
                 'number_rules_sha256': number_hash, 'version': VERSION}
    result = dict(version=VERSION, recovery_review=VERSION, policy_sha256=digest(effective),
                  observation_sha256=digest(observed), target_id=target['target_id'],
                  target_descriptor=target, status='UNKNOWN', checked_rules=[],
                  unsupported_reasons=[], witnesses=[], full_EA_verdict='NOT_EVALUATED')
    if not effective['enabled']:
        result['unsupported_reasons'] = ['POLICY_DISABLED']
        return result
    if set(effective['rules']) - set(RULES) or not effective['rules']:
        result['unsupported_reasons'] = ['UNSUPPORTED_RULE_SELECTION']
        return result
    context = observed['context']

    def cite(start, end, field='context'):
        text = observed[field][start:end]
        if not text.strip():
            raise ValueError('EMPTY_RECOVERY_CITATION')
        return {'field': field, 'span': [start, end], 'quote': text}

    def number(text):
        normalized, _ = normalize_number(text.strip(), rules)
        if len(re.sub(r'\D', '', normalized)) > 18:
            raise ValueError('NUMBER_PRECISION_OUT_OF_SCOPE')
        value = Decimal(normalized)
        if not value.is_finite():
            raise ValueError('NONFINITE_RECOVERY_NUMBER')
        return value

    def witness(rule, expression, value, evidence, assumptions):
        result['witnesses'].append(dict(rule=rule, expression=expression, recovered_value=str(value),
            entity=target['entity'], period=target['period'], unit=target['unit'],
            evidence=evidence, assumptions=assumptions))

    try:
        if target['kind'] == 'current_tax' and 'current_tax_subtotal' in effective['rules']:
            result['checked_rules'].append('current_tax_subtotal')
            matches = list(TAX.finditer(context))
            if len(matches) != 1:
                raise ValueError('UNSUPPORTED_OR_MULTIPLE_TAX_BLOCKS')
            match = matches[0]
            intro = tax_intro(context, match)
            if target['entity'] != (intro['company'] or 'company') or target['unit'] != 'USD' or target['item'] not in ('State', 'Federal'):
                raise ValueError('TARGET_SCOPE_MISMATCH')
            if match['year1'] == match['year2'] or target['period'] not in (match['year1'], match['year2']):
                raise ValueError('PERIOD_MISMATCH')
            if '$' not in match[0]:
                raise ValueError('TAX_RELATION_OR_CURRENCY_UNCONFIRMED')
            if re.search(r'(?i)rounded|approximately|thousands|millions|CAD|AUD', context):
                raise ValueError('UNSUPPORTED_SCALE_OR_ROUNDING')
            col = 1 if target['period'] == match['year1'] else 2
            missing = ('s' if target['item'] == 'State' else 'f') + str(col)
            other = ('f' if target['item'] == 'State' else 's') + str(col)
            total = 't' + str(col)
            if match[missing].strip():
                raise ValueError('TARGET_NOT_EMPTY')
            if not all(re.fullmatch(r'\$?' + NUM, match[key].strip()) for key in (other, total)):
                raise ValueError('MULTIPLE_UNKNOWNS_OR_UNSUPPORTED_NUMBER')
            whole, part = number(match[total]), number(match[other])
            value = whole - part
            witness('current_tax_subtotal', f'{whole} - {part}', value,
                    [cite(*match.span()), cite(*match.span(total)), cite(*match.span(other)),
                     cite(*intro.span())],
                    ['Reviewed adjacent Current Federal/State rows form the following unlabeled subtotal.',
                     'Dollar-denominated unscaled table; same year column; exactly one unknown.'])
            # A second, explicitly bounded step answers only this exact average question.
            owner = "the company's" if target['entity'] == 'company' else target['entity'] + "'s"
            q = 'What is ' + owner + ' average current state tax expense between '
            years = sorted((match['year1'], match['year2']))
            other_state = 's' + str(3 - col)
            if (target['item'] == 'State' and ' '.join(observed['question'].split()) == q + ' and '.join(years) + '?'
                    and re.fullmatch(NUM, match[other_state].strip())):
                previous = number(match[other_state])
                result['witnesses'][-1]['derived_answer'] = {
                    'expression': f'({value} + {previous}) / 2', 'value': str((value + previous) / Decimal(2)),
                    'evidence': [cite(*match.span(other_state)), cite(0, len(observed['question']), 'question')]}
        elif target['kind'] == 'portfolio_weight' and 'closed_three_asset_weights' in effective['rules']:
            result['checked_rules'].append('closed_three_asset_weights')
            if target['entity'] != 'portfolio' or target['period'] != 'allocation' or target['unit'] != '%':
                raise ValueError('TARGET_SCOPE_MISMATCH')
            closed, names, weight_pattern = portfolio_parts(context)
            if re.search(r'(?i)approximately|rounded|about|cash|other assets|remaining assets|short|leverage', context):
                raise ValueError('OPEN_OR_APPROXIMATE_PORTFOLIO')
            allocations = list(ALLOCATION.finditer(context))
            if len(allocations) != 1:
                raise ValueError('AMBIGUOUS_ALLOCATION')
            allocation = allocations[0]
            actor = ' '.join(allocation['actor'].split())
            if actor != (closed['manager'] or 'The investor'):
                raise ValueError('PORTFOLIO_OWNER_MISMATCH')
            weights = list(weight_pattern.finditer(allocation[0]))
            if len(weights) != 2 or len({w['asset'] for w in weights}) != 2:
                raise ValueError('REQUIRE_EXACTLY_TWO_KNOWN_WEIGHTS')
            expected = set(names) - {w['asset'] for w in weights}
            if expected != {target['item']}:
                raise ValueError('TARGET_SCOPE_MISMATCH')
            # Accept only the two reviewed sentence prefixes and allocation clauses.
            remainder = weight_pattern.sub('', allocation[0])
            remainder = re.sub(r'^.*?\bhas\s+allocated\s+their\s+portfolio\s+', '', remainder)
            remainder = re.sub(r'\s+', ' ', remainder)
            for prefix in ('such that ', f'among {names[0]}, {names[1]}, and {names[2]}, with '):
                if remainder.startswith(prefix):
                    remainder = remainder[len(prefix):]
                    break
            else:
                raise ValueError('UNREGISTERED_ALLOCATION_GRAMMAR')
            # The planning preview may retain a value-free target clause.
            remainder = re.sub(r'(?:is invested )?in ' + re.escape(target['item']), '', remainder)
            if re.sub(r'\band\b|[\s,.]', '', remainder):
                raise ValueError('UNREGISTERED_ALLOCATION_GRAMMAR')
            values = [number(w['amount']) for w in weights]
            if any(v < 0 or v > 100 for v in values) or sum(values) > 100:
                raise ValueError('INCONSISTENT_WEIGHTS')
            value = Decimal(100) - sum(values)
            witness('closed_three_asset_weights', '100 - ' + ' - '.join(map(str, values)), value,
                    [cite(*closed.span()), cite(*allocation.span())] +
                    [cite(allocation.start() + w.start(), allocation.start() + w.end()) for w in weights],
                    ['The explicitly enumerated three assets exhaust this portfolio allocation.',
                     'Two exact allocation percentages are known; only the target weight is unknown.'])
        else:
            raise ValueError('UNREGISTERED_TARGET_OR_RULE')
    except (ValueError, ArithmeticError) as error:
        result['witnesses'] = []
        result['unsupported_reasons'].append(str(error))
    if result['witnesses']:
        result['status'] = 'RECOVERABLE'
        result['perturbation_validity'] = 'INVALID'
    elif not result['unsupported_reasons']:
        result['status'] = 'NO_WITNESS_IN_SCOPE'
    result['unsupported_reasons'].append('DIRECT_RESTATEMENT_AND_GENERIC_RELATIONS_NOT_IMPLEMENTED')
    return result
