"""Exact bounded inversion of existing graph equations with surviving Q/C bindings."""
import ast
from fractions import Fraction
from finarch.dataset.shared.calculation.number_normalization import load_rules, normalize_number
from finarch.dataset.schemas.validation import validate
from finarch.dataset.shared.review.dtt_audit import observation_hash

VERSION = 'BOUNDED_EQUATION_V2'
MAX_NODES = 128
MAX_STEPS = 32


def recovery_inputs(program, target):
    # No numeric values, gold, computed traces, or target fact enter this contract.
    return {'facts': {key: {k: fact[k] for k in ('span', 'text', 'origin') if k in fact}
                      for key, fact in program['facts'].items() if key != target},
            'bindings': [{k: b[k] for k in ('variable', 'field', 'span', 'text') if k in b}
                         for b in program.get('recovery_bindings', [])]}


def screen(observation, source, patches, graph, target, inputs):
    result = dict(version=VERSION, status='NOT_EVALUATED', target_id=target,
                  observation_sha256=observation_hash(observation), witnesses=[],
                  unsupported_reasons=[], full_EA_verdict='NOT_EVALUATED',
                  limits={'nodes': MAX_NODES, 'steps': MAX_STEPS})
    try:
        validate('02-generation.03-validation.ea-recovery-bindings', inputs.get('bindings', []))
        rules, rules_hash = load_rules()
        result['number_rules_sha256'] = rules_hash
        result['number_normalization'] = []
        if observation['question'] != source['question']:
            raise ValueError('QUESTION_CHANGED')
        if len(patches) != 1:
            raise ValueError('ONE_DELETION_PATCH_REQUIRED')
        patch = patches[0]; start, end = patch['start'], patch['end']
        if not (type(start) is type(end) is int and 0 <= start < end <= len(source['context'])):
            raise ValueError('INVALID_PATCH')
        if (source['context'][start:end] != patch['before'] or
                source['context'][:start] + patch['text'] + source['context'][end:] != observation['context']):
            raise ValueError('PATCH_MISMATCH')

        def cite(binding):
            field = binding.get('field', 'question' if binding.get('origin') == 'QUESTION' else 'context')
            if field not in ('question', 'context'): raise ValueError('INVALID_BINDING_FIELD')
            left, right = binding['span']
            if not (type(left) is type(right) is int and 0 <= left < right <= len(source[field])):
                raise ValueError('INVALID_BINDING_SPAN')
            text = binding['text']
            if source[field][left:right] != text: raise ValueError('BINDING_TEXT_MISMATCH')
            if field == 'context':
                if left < end and start < right: raise ValueError('BINDING_IN_DELETED_REGION')
                if left >= end:
                    left += len(patch['text']) - (end-start); right += len(patch['text']) - (end-start)
            if observation[field][left:right] != text: raise ValueError('BINDING_NOT_SURVIVING')
            import re
            steps = []
            token, applied = normalize_number(text, rules, steps)
            result['number_normalization'].append({'source_text': text, 'normalized': token,
                                                    'applied_rules': applied, 'steps': steps})
            if len(token) > 32 or not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)', token):
                raise ValueError('UNSUPPORTED_BOUND_NUMBER')
            return Fraction(token), {'field': field, 'span': [left, right], 'quote': text}

        nodes = {n['id']: n for n in graph['nodes']}
        if not nodes or len(nodes) != len(graph['nodes']) or len(nodes) > MAX_NODES:
            raise ValueError('GRAPH_BOUND_OR_DUPLICATE')
        missing = [n for n in nodes.values() if n.get('fact_id') == target]
        if not missing: raise ValueError('MISSING_TARGET_NODE')
        evidence = []; known = {}
        for key, node in nodes.items():
            if node['kind'] == 'fact' and node.get('fact_id') != target:
                fact = inputs.get('facts', {}).get(node.get('fact_id'))
                if fact:
                    known[key], citation = cite(fact); evidence.append(citation)
        bindings = inputs.get('bindings', [])
        if not bindings: raise ValueError('NO_EXPLICIT_INDEPENDENT_RHS_BINDING')

        def expr(key, stack=()):
            if key in stack or len(stack) > MAX_STEPS: raise ValueError('CYCLE_OR_DEPTH_BOUND')
            n = nodes[key]; kind = n['kind']; parents = n.get('inputs', [])
            if kind == 'fact':
                if parents: raise ValueError('INVALID_FACT')
                if n.get('fact_id') == target: return ('x',)
                if key not in known: raise ValueError('UNBOUND_SURVIVING_FACT')
                return ('n', known[key])
            if kind == 'constant':
                literal = ast.parse(n['expression'], mode='eval').body
                if not isinstance(literal, ast.Constant) or type(literal.value) not in (int, float):
                    raise ValueError('UNSUPPORTED_LITERAL')
                text = ast.get_source_segment(n['expression'], literal)
                if len(text) > 32: raise ValueError('LITERAL_BOUND')
                return ('n', Fraction(text))
            if kind == 'variable' and len(parents) == 1: return expr(parents[0], (*stack, key))
            if kind != 'operation' or n.get('operator') not in ('+', '-', '*', '/') or len(parents) != 2:
                raise ValueError('UNSUPPORTED_EQUATION_STRUCTURE')
            return (n['operator'], *(expr(p, (*stack, key)) for p in parents))

        def count(e): return 1 if e[0] == 'x' else 0 if e[0] == 'n' else count(e[1])+count(e[2])
        def bounded(v):
            if max(v.numerator.bit_length(), v.denominator.bit_length()) > 4096: raise ValueError('ARITHMETIC_BOUND')
            return v
        def evaluate(e, x=None):
            if e[0] == 'x': return x
            if e[0] == 'n': return e[1]
            a, b = evaluate(e[1], x), evaluate(e[2], x)
            if e[0] == '+': return bounded(a+b)
            if e[0] == '-': return bounded(a-b)
            if e[0] == '*': return bounded(a*b)
            if b == 0: raise ValueError('DIVISION_BY_ZERO')
            return bounded(a/b)
        def invert(e, rhs, steps):
            if len(steps) >= MAX_STEPS: raise ValueError('STEP_BOUND')
            if e[0] == 'x': return rhs
            op, a, b = e; left = count(a) == 1; other = evaluate(b if left else a)
            if op == '+': value = rhs-other
            elif op == '-': value = rhs+other if left else other-rhs
            elif op == '*':
                if other == 0: raise ValueError('NON_UNIQUE_OR_INCONSISTENT_ZERO_PRODUCT')
                value = rhs/other
            elif left:
                if other == 0: raise ValueError('DIVISION_BY_ZERO')
                value = rhs*other
            else:
                if rhs == 0 or other == 0: raise ValueError('NON_UNIQUE_OR_INCONSISTENT_ZERO_QUOTIENT')
                value = other/rhs
            steps.append({'operator': op, 'unknown_side': 'left' if left else 'right',
                          'rhs': str(rhs), 'known_operand': str(other), 'inverse_result': str(value)})
            return invert(a if left else b, bounded(value), steps)

        candidates = []
        for binding in bindings:
            variable = binding['variable']
            key = graph['variables'].get(variable)
            if key not in nodes or nodes[key].get('variable') != variable:
                raise ValueError('UNBOUND_EQUATION_VARIABLE')
            expression = expr(key)
            if count(expression) != 1: raise ValueError('EXACTLY_ONE_UNKNOWN_OCCURRENCE_REQUIRED')
            rhs, citation = cite(binding); steps = []
            recovered = invert(expression, rhs, steps)
            if evaluate(expression, recovered) != rhs: raise ValueError('SUBSTITUTION_MISMATCH')
            candidates.append({'variable': variable, 'recovered_value': str(recovered), 'rhs': str(rhs),
                               'steps': steps, 'evidence': [*evidence, citation]})
        if len({c['recovered_value'] for c in candidates}) != 1:
            raise ValueError('INCONSISTENT_BINDINGS')
        result.update(status='RECOVERABLE', witnesses=candidates, perturbation_validity='INVALID')
    except (KeyError, TypeError, ValueError, ArithmeticError, SyntaxError, RecursionError) as error:
        result['unsupported_reasons'] = [str(error)]
    return result
