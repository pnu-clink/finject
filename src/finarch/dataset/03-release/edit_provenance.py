"""Reconstruct saved edits without changing the problem or judging its answer."""
import copy
import hashlib
import json
from pathlib import Path

SOURCE_PARENTS = {'IC_SOURCE_A_ONLY': 'IC_VALUE_01_BEFORE',
                  'IC_SOURCE_B_ONLY': 'IC_VALUE_01_AFTER'}


def text_sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest() if isinstance(text, str) else None


def qc_hashes(row):
    return {key + '_sha256': text_sha(row.get(key)) for key in ('question', 'context')}


def apply_patches(context, patches):
    """Apply half-open Python/Unicode offsets against one pre-edit context."""
    if not isinstance(patches, list):
        raise ValueError('PATCH_LIST_REQUIRED')
    checked = []
    for patch in patches:
        if not isinstance(patch, dict):
            raise ValueError('INVALID_PATCH')
        start, end = patch.get('start'), patch.get('end')
        if type(start) is not int or type(end) is not int or not 0 <= start <= end <= len(context):
            raise ValueError('PATCH_RANGE_INVALID')
        if not isinstance(patch.get('before'), str) or context[start:end] != patch['before']:
            raise ValueError('PATCH_BEFORE_MISMATCH')
        segments, text = patch.get('segments'), patch.get('text')
        if (not isinstance(text, str) or not isinstance(segments, list) or not segments or
                any(not isinstance(s, dict) or not isinstance(s.get('text'), str) or
                    not isinstance(s.get('kind'), str) or not s['kind'] for s in segments)):
            raise ValueError('PATCH_SEGMENTS_REQUIRED')
        if ''.join(segment['text'] for segment in segments) != text:
            raise ValueError('PATCH_SEGMENTS_MISMATCH')
        checked.append(patch)
    checked.sort(key=lambda p: (p['start'], p['end']))
    for previous, current in zip(checked, checked[1:]):
        if current['start'] < previous['end'] or current['start'] == previous['start']:
            raise ValueError('PATCH_OVERLAP')
    for patch in reversed(checked):
        context = context[:patch['start']] + patch['text'] + context[patch['end']:]
    return context


def build(case, variant, baseline, final, comparison=None, source=None):
    """Create one explicit VERIFIED/UNAVAILABLE/MISMATCH record for an export row."""
    result = {'schema_version': 1, 'status': 'UNAVAILABLE', 'reason': None,
              'offset_unit': 'unicode_code_point',
              'baseline': {'case': case, 'variant': 'ORIGINAL', **qc_hashes(baseline)},
              'final': qc_hashes(final), 'steps': [], 'source': source or {}}
    if not all(isinstance(row.get(key), str) and row[key].strip()
               for row in (baseline, final) for key in ('question', 'context')):
        result['reason'] = 'NO_SAVED_QUESTION_CONTEXT'
        return result
    if variant != 'ORIGINAL' and not isinstance(comparison, dict):
        result['reason'] = 'NO_SAVED_COMPARISON'
        return result
    if variant != 'ORIGINAL':
        chain = []
        if variant in SOURCE_PARENTS:
            chain.append((SOURCE_PARENTS[variant], comparison.get('value_dependency')))
        chain.append((variant, comparison.get('patches')))
        result['steps'] = [{'variant': label, 'input_context_sha256': None,
                            'output_context_sha256': None, 'patches': copy.deepcopy(patches)}
                           for label, patches in chain]
        if any(not isinstance(step['patches'], list) for step in result['steps']):
            result['reason'] = 'NO_SAVED_PATCHES'
            return result
    try:
        if baseline['question'] != final['question']:
            raise ValueError('QUESTION_CHANGED_WITHOUT_PATCH_RECORD')
        if variant != 'ORIGINAL':
            for key in ('question', 'context'):
                if comparison.get('reference', {}).get(key) != baseline[key]:
                    raise ValueError('BASELINE_COMPARISON_MISMATCH')
                if comparison.get('working', {}).get(key) != final[key]:
                    raise ValueError('FINAL_COMPARISON_MISMATCH')
        context = baseline['context']
        for step in result['steps']:
            step['input_context_sha256'] = text_sha(context)
            context = apply_patches(context, step['patches'])
            step['output_context_sha256'] = text_sha(context)
        if context != final['context']:
            raise ValueError('RECONSTRUCTED_CONTEXT_MISMATCH')
        result['status'] = 'VERIFIED'
    except (ValueError, TypeError, AttributeError, KeyError) as error:
        result.update(status='MISMATCH', reason=str(error))
    return result


def from_file(run, case, variant, baseline, final, comparison_path=None):
    """Bind the record to the exact saved comparison file, if available."""
    run = Path(run).resolve()
    comparison, source = None, {}
    if comparison_path is not None:
        path = Path(comparison_path).resolve()
        if not path.is_relative_to(run):
            raise ValueError('COMPARISON_OUTSIDE_DATASET_RUN')
        source['comparison'] = str(path.relative_to(run))
        if path.exists():
            raw = path.read_bytes()
            source['comparison_sha256'] = hashlib.sha256(raw).hexdigest()
            try:
                comparison = json.loads(raw)
            except (ValueError, UnicodeError):
                result = build(case, variant, baseline, final, source=source)
                result.update(status='MISMATCH', reason='INVALID_COMPARISON_JSON')
                return result
    return build(case, variant, baseline, final, comparison, source)


def checked(record, case, variant, baseline, final):
    """Recheck exported provenance against the exact experiment Q/C."""
    if not isinstance(record, dict):
        result = build(case, variant, baseline, final)
        result.update(status='UNAVAILABLE', reason='NO_EXPORTED_EDIT_PROVENANCE')
        return result
    result = copy.deepcopy(record)
    try:
        if result.get('schema_version') != 1 or result.get('offset_unit') != 'unicode_code_point':
            raise ValueError('UNSUPPORTED_EDIT_PROVENANCE')
        if result.get('baseline') != {'case': case, 'variant': 'ORIGINAL', **qc_hashes(baseline)}:
            raise ValueError('EXPERIMENT_BASELINE_MISMATCH')
        if result.get('final') != qc_hashes(final):
            raise ValueError('EXPERIMENT_FINAL_MISMATCH')
        if result.get('status') in ('UNAVAILABLE', 'MISMATCH'):
            return result
        if result.get('status') != 'VERIFIED':
            raise ValueError('INVALID_PROVENANCE_STATUS')
        expected = [] if variant == 'ORIGINAL' else [variant]
        if variant in SOURCE_PARENTS:
            expected.insert(0, SOURCE_PARENTS[variant])
        steps = result.get('steps')
        if not isinstance(steps, list) or any(not isinstance(s, dict) for s in steps):
            raise ValueError('INVALID_EDIT_STEPS')
        if [step.get('variant') for step in steps] != expected:
            raise ValueError('EDIT_STEP_ORDER_MISMATCH')
        context = baseline['context']
        for step in steps:
            if step.get('input_context_sha256') != text_sha(context):
                raise ValueError('EDIT_INPUT_HASH_MISMATCH')
            context = apply_patches(context, step.get('patches'))
            if step.get('output_context_sha256') != text_sha(context):
                raise ValueError('EDIT_OUTPUT_HASH_MISMATCH')
        if context != final['context'] or baseline['question'] != final['question']:
            raise ValueError('RECONSTRUCTED_CONTEXT_MISMATCH')
    except (ValueError, KeyError, TypeError) as error:
        result.update(status='MISMATCH', reason=str(error))
    return result
