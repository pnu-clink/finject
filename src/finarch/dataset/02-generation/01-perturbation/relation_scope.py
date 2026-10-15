"""Bounded relation selection from explicit source-table cells, not financial inference."""
import ast
from copy import deepcopy
from decimal import Decimal
from importlib import import_module
from heapq import nsmallest
import re

from finarch.dataset.shared.calculation.number_normalization import load_rules, normalize_number

VERSION = 'source-scoped-relation-v2'
LIMIT = 64
NUMERIC_RULE = 'Use only the numbers in allowed_numbers.'
YEAR = re.compile(r'(?<!\d)(?:19|20)\d{2}(?!\d)')


def numeric(text, rules):
    """Use registered number rules; leave ambiguous parenthesized cells unselected."""
    raw = text.strip()
    if raw.startswith('('):
        return None
    raw = re.sub(r'^[\$£€¥]\s*', '', raw).rstrip('%').strip()
    # Labels and dates (e.g. December 28, 2018) are not scalar amounts.
    if not re.fullmatch(r'[+-]?(?=[\d.,]*\d)[\d.,]+(?:[eE][+-]?\d+)?', raw):
        return None
    value, _ = normalize_number(raw, rules, [])
    return value if re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?', value) else None


def fact_decimal(value):
    """Normalize private arithmetic inputs with the same registered runtime rules."""
    normalized, _ = normalize_number(str(value), load_rules()[0], [])
    return Decimal(normalized)


def source_cells(context):
    """Read flat quantity/year JSON or Markdown tables without changing source offsets."""
    cells = []
    if context.lstrip().startswith('{'):
        parser = import_module('finarch.dataset.00-input.json_context')
        try:
            root = parser.parse(context)
        except parser.JsonContextError:
            return cells
        if root.kind != 'object':
            return cells
        for key, row in root.children:
            if row.kind != 'object':
                continue
            group, sep, label = key.value.partition(' -- ')
            for period, node in row.children:
                if node.kind not in ('integer', 'number'):
                    continue
                cells.append({'quantity': label if sep else key.value,
                              'group': group if sep else None, 'table': group if sep else 'json',
                              'period': period.value, 'span': [node.start, node.end],
                              'text': context[node.start:node.end], 'value': str(node.value)})
        return cells
    heading = None
    header = None
    table = -1
    offset = 0
    rules = load_rules()[0]
    for line in context.splitlines(keepends=True):
        pipes = [m.start() for m in re.finditer(r'(?<!\\)\|', line)]
        if len(pipes) < 2:
            if line.strip():
                heading = line.strip().lstrip('#').strip()
            header = None
            offset += len(line)
            continue
        fields = []
        for a, b in zip(pipes, pipes[1:]):
            raw = line[a + 1:b]
            start = offset + a + 1 + len(raw) - len(raw.lstrip())
            fields.append((raw.strip(), [start, start + len(raw.strip())]))
        if all(re.fullmatch(r':?-+:?', text) for text, _ in fields):
            offset += len(line)
            continue
        if header is None:
            header = [text for text, _ in fields]
            table += 1
        elif len(fields) == len(header):
            label = fields[0][0]
            group, sep, label_tail = label.partition(' -- ')
            # A heading establishes a group only if the table explicitly names its total.
            group = group if sep else heading
            for column, (text, span) in enumerate(fields[1:], 1):
                value = numeric(text, rules)
                if value is not None:
                    cells.append({'quantity': label_tail if sep else label, 'group': group,
                                  'table': str(table), 'period': header[column],
                                  'span': span, 'text': text, 'value': value})
        offset += len(line)
    return cells


def total(cell):
    group = cell.get('group')
    return bool(group and cell['quantity'].casefold() == ('total ' + group).casefold())


def descriptors(context, program):
    """Enrich existing inputs and retain same-row alternatives with exact source evidence."""
    cells = source_cells(context)
    original = []
    for key, fact in sorted(program['facts'].items(), key=lambda pair: pair[1]['span'][0]):
        matched = next((c for c in cells if fact.get('origin', 'CONTEXT') == 'CONTEXT'
                        and c['span'][0] <= fact['span'][0] < fact['span'][1] <= c['span'][1]
                        and Decimal(c['value']) == fact_decimal(fact['value'])), None)
        named_years = YEAR.findall(key)
        named_period = named_years[0] if len(named_years) == 1 and named_years[0] in YEAR.findall(context) else None
        grouped_total = matched and any(c.get('group') == matched.get('group') and c['table'] == matched['table'] and total(c) for c in cells)
        original.append({**(matched or {}), 'fact_id': key, 'fact': fact,
                         'period': matched['period'] if matched else named_period,
                         'period_evidence': 'TABLE_HEADER' if matched else 'UPSTREAM_FACT_ID_AND_CONTEXT' if named_period else 'UNKNOWN',
                         'aggregation_role': 'TOTAL' if matched and total(matched) else 'COMPONENT' if grouped_total else 'UNKNOWN'})
    inventory = list(original)
    seen = {(f['fact'].get('origin', 'CONTEXT'), tuple(f.get('span', f['fact']['span']))) for f in original}
    for descriptor in original:
        if 'table' not in descriptor:
            continue
        for cell in cells:
            identity = ('CONTEXT', tuple(cell['span']))
            if identity in seen or any(cell.get(k) != descriptor.get(k) for k in ('table', 'group', 'quantity')):
                continue
            if cell['period'] == descriptor['period']:
                continue
            seen.add(identity)
            key = f"relation_reference_{cell['span'][0]}_{cell['span'][1]}"
            fact = {k: cell[k] for k in ('span', 'text', 'value')}
            fact.update(unit=descriptor['fact'].get('unit'), origin='CONTEXT')
            inventory.append({**cell, 'fact_id': key, 'fact': fact,
                              'aggregation_role': descriptor['aggregation_role'], 'period_evidence': 'TABLE_HEADER'})
    return original, inventory, cells


def candidates(context, program):
    original, inventory, cells = descriptors(context, program)
    pairs = ((left, right) for left in original for right in inventory
             if left['fact_id'] != right['fact_id']
             and (left['fact'].get('unit') or '') == (right['fact'].get('unit') or ''))
    def order(pair):
        left, right = pair
        left_years, right_years = set(YEAR.findall(left['period'] or '')), set(YEAR.findall(right['period'] or ''))
        cross = bool(left_years and right_years and left_years.isdisjoint(right_years))
        return (not cross, left['fact']['span'][0], right['fact']['span'][0])
    return nsmallest(LIMIT, pairs, key=order), cells


def check_structure(left, right, factor, cells):
    """Apply only explicitly grouped, nonnegative part/total bounds."""
    factor = Decimal(factor)
    if not factor.is_finite() or factor <= 0:
        raise ValueError('RELATION_INVALID_COEFFICIENT')
    group = left.get('group')
    if group and group == right.get('group') and total(right) and not total(left):
        raise ValueError('RELATION_TOTAL_MUST_BE_LEFT')
    derived = fact_decimal(right['fact']['value']) * factor
    if derived == fact_decimal(left['fact']['value']):
        raise ValueError('RELATION_ALREADY_CONSISTENT')
    if not group:
        return
    peers = [c for c in cells if all(c.get(k) == left.get(k) for k in ('table', 'group', 'period'))]
    whole = next((c for c in peers if total(c)), None)
    if not whole or not peers or any(Decimal(c['value']) < 0 for c in peers):
        return
    if total(left):
        if any(derived < Decimal(c['value']) for c in peers if not total(c)):
            raise ValueError('RELATION_TOTAL_BELOW_COMPONENT')
    elif derived > Decimal(whole['value']):
        raise ValueError('RELATION_COMPONENT_EXCEEDS_TOTAL')


def add_reference(program, right):
    """Add a source-bound input to a private copy; keep original code and facts intact."""
    if right['fact_id'] in program['facts']:
        if program['facts'][right['fact_id']] != right['fact']:
            raise ValueError('RELATION_REFERENCE_ID_COLLISION')
        return program
    tree = ast.parse(program['code'])
    last = max((i for i, node in enumerate(tree.body) if isinstance(node, ast.Assign)
                and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name)
                and node.value.func.id == 'fact'), default=-1)
    if last < 0:
        raise ValueError('RELATION_BINDING_INCOMPLETE')
    key = right['fact_id']
    if any(isinstance(node, ast.Name) and node.id == key for node in ast.walk(tree)):
        raise ValueError('RELATION_NAME_COLLISION')
    tree.body.insert(last + 1, ast.parse(f'{key} = fact({key!r})').body[0])
    expanded = deepcopy(program)
    expanded['facts'][key] = deepcopy(right['fact'])
    expanded['code'] = ast.unparse(tree)
    return expanded


def contract(left, right, factor):
    allowed = [str(factor), str(right['fact']['value'])]
    for descriptor in (left, right):
        for label in (descriptor.get('quantity'), descriptor.get('period')):
            allowed += re.findall(r'(?<![\w.])\d+(?:\.\d+)?(?!\w)', label or '')
    relation = {'target': left['fact'], 'operand': right['fact'], 'factor': str(factor),
                'operation': 'multiply', 'operand_scope': 'original observed quantity',
                'target_quantity': left.get('quantity'), 'target_period': left.get('period'),
                'operand_quantity': right.get('quantity'), 'operand_period': right.get('period'),
                'target_group': left.get('group'), 'target_aggregation_role': left.get('aggregation_role', 'UNKNOWN'),
                'operand_group': right.get('group'), 'operand_aggregation_role': right.get('aggregation_role', 'UNKNOWN'),
                'target_value_in_sentence': 'FORBIDDEN', 'reference_value_in_sentence': 'PERMITTED'}
    instruction = ('Begin with a space and express the supplied relation naturally. Preserve all original observations. '
                   'Identify the left target by quantity and period only; never repeat its observed amount. '
                   'The right reference amount may be stated. ' + NUMERIC_RULE)
    return relation, instruction, list(dict.fromkeys(allowed))
