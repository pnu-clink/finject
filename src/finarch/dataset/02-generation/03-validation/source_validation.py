"""Validate attribution removal against the saved, assigned VALUE dependency."""
from finarch.dataset.shared.review.dtt_audit import observation_hash


def validate(plan, request, response, observation, patches, base, dependency, index):
    result = {'version': 'SOURCE_EXACT_V1', 'status': 'FAIL', 'checks': {},
              'observation_sha256': observation_hash(observation)}
    def require(name, condition):
        result['checks'][name] = bool(condition)
        if not condition: raise ValueError(name)
    try:
        label = 'IC_VALUE_01_AFTER' if index == 3 else 'IC_VALUE_01_BEFORE'
        require('assigned_base', index in (2, 3) and base.get('label') == label and
                plan['intent'].get('base_variant') == label and base.get('status') == 'PASS')
        value = base['observation']; base_hash = observation_hash(value)
        result['base_observation_sha256'] = base_hash
        require('dependency_path', bool(base.get('path')) and dependency.get('source') == base['path'])
        require('dependency_hash', dependency.get('observation_sha256') == base_hash)
        require('request_base_exact', all(request[k] == value[k] for k in ('context', 'question')))
        require('question_exact', observation['question'] == value['question'] == plan['request']['question'])
        require('one_saved_patch', len(patches) == 1 and response.get('patches') == [{k: p.get(k) for k in ('start', 'end', 'before', 'element_ids', 'text')} for p in patches] and len(request['edit_slots']) == 1)
        patch, slot = patches[0], request['edit_slots'][0]
        position = patch['start']; text = patch['text']
        require('insertion_contract', type(position) is int and patch['end'] == position and patch['before'] == '' and
                slot['start'] == slot['end'] == position and slot['before'] == '' and
                0 <= position <= len(value['context']) and isinstance(text, str) and bool(text.strip()) and
                patch.get('element_ids') == slot.get('element_ids'))
        # Recompute the authorized claim boundary from the current assigned VALUE.
        from importlib import import_module
        from copy import deepcopy
        expected = import_module('finarch.dataset.02-generation.01-perturbation.generation_plan').source_request(deepcopy(plan), base)
        require('assigned_position', expected['edit_slots'][0] == slot)
        require('saved_text_at_position', observation['context'][position:position+len(text)] == text)
        restored = observation['context'][:position] + observation['context'][position+len(text):]
        require('restored_context_exact', restored == value['context'])
        result.update(status='PASS', reason='Attribution-only removal exactly reproduces the assigned VALUE Q/C.',
                      removed={'start': position, 'end': position+len(text), 'text': text})
    except (KeyError, TypeError, ValueError, IndexError) as error:
        result['reason'] = 'IC_SOURCE_EXACT_MISMATCH:' + str(error)
    return result
