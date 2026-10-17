"""Display a complete, copyable calculation program without rewriting model output."""
import copy
import hashlib
from pprint import pformat

from finarch.dataset.shared.calculation.number_normalization import prepare_numeric_values


def render_standalone(program, normalization=None):
    # [PX01] docs/02-architecture.md#PX01 It composes independent computational code, including data, functions, and inputs.
    prepared = copy.deepcopy(program)
    if normalization is not None:
        if normalization.get('status') != 'PASS':
            raise ValueError('NUMBER_NORMALIZATION_NOT_PASSED')
        rows = {row['fact_id']: row for row in normalization['facts']}
        if set(rows) != set(prepared['facts']):
            raise ValueError('NORMALIZATION_FACTS_MISMATCH')
        for key, fact in prepared['facts'].items():
            row = rows[key]
            if row['original_value'] != fact['value'] or not isinstance(row['python_value'], str):
                raise ValueError('NORMALIZATION_VALUE_MISMATCH')
            fact['value'] = row['python_value']
    else:
        prepared, audit, _ = prepare_numeric_values(prepared)
        if audit['status'] != 'PASS':
            raise ValueError('NUMBER_NORMALIZATION_NOT_PASSED')

    values = {key: fact['value'] for key, fact in prepared['facts'].items()}
    # Validate before offering a runnable calculation; never substitute missing values.
    for value in values.values():
        float(value)
    data = pformat(values, width=80, sort_dicts=False)
    prefix = '\n'.join([
        '# Standalone calculation — Python 3, no external packages required',
        '# Source-span validation and reference comparison are separate pipeline checks.',
        '# The values below are calculation inputs normalized from the saved facts.',
        'import math', 'from decimal import Decimal', 'from fractions import Fraction',
        '', '_finarch_fact_values = ' + data, '',
        'def fact(name):',
        '    """Return the calculation value for the given fact key."""',
        '    if name not in _finarch_fact_values:',
        '        raise ValueError("UNKNOWN_FACT: " + str(name))',
        '    return float(_finarch_fact_values[name])', '',
        '# ----- Saved calculation code begins -----', '',
    ])
    code = prefix + program['code'] + '\n# ----- Saved calculation code ends -----\n\nprint(answer)\n'
    return {'code': code, 'original_start_line': len(prefix.splitlines()) + 1,
            'source_code_sha256': hashlib.sha256(program['code'].encode()).hexdigest(),
            'purpose': 'CALCULATION_ONLY', 'fact_values': values}
