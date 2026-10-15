"""Preserve originals while validating bounded source and arithmetic repairs."""
import copy
import re
from finarch.dataset.shared.prompts import read_prompt
from pathlib import Path
from importlib import import_module

from finarch.shared.providers.cli import call
from finarch.dataset.shared.review.dtt_audit import audit_one, observation_hash
from finarch.dataset.schemas.llm import executable_program
name_constants = __import__('finarch.dataset.02-generation.operations.stepwise', fromlist=['name_constants']).name_constants
from finarch.dataset.shared.calculation.python_runtime import execute
from finarch.shared.reference import Reference, compare, normalize


REVISION_PROMPT = read_prompt('01-preparation.02-review-and-correct.revision.md')

EVIDENCE_PROMPT = read_prompt('01-preparation.03-calculation.review-answer-evidence.md')


def invoke(ctx, config, stage, role, request, instruction):
    def handler(payload, *, response_schema):
        return call(config, role, payload, instruction=instruction,
                    save=lambda name, value: ctx.save(stage + '/03-LLM-call/' + name, value))
    return ctx.invoke(stage, '01-request', role, request, local=handler)


def apply_revision(sample, response):
    if response['disposition'] != 'REVISED' or not response['edits']:
        raise ValueError('SOURCE_REVISION_UNRESOLVED')
    revised = copy.deepcopy(sample)
    for field in ('context', 'question'):
        text = sample[field]
        edits = []
        for proposed in response['edits']:
            if proposed['field'] != field:
                continue
            edit = dict(proposed)
            start, end = edit['start'], edit['end']
            if not 0 <= start <= end <= len(text) or text[start:end] != edit['before']:
                if not edit['before'] or text.count(edit['before']) != 1:
                    raise ValueError('AMBIGUOUS_SOURCE_REVISION_ANCHOR')
                edit['start'] = text.index(edit['before'])
                edit['end'] = edit['start'] + len(edit['before'])
            edits.append(edit)
        edits.sort(key=lambda edit: edit['start'])
        last = -1
        for edit in edits:
            start, end = edit['start'], edit['end']
            if not 0 <= start <= end <= len(text) or start <= last or text[start:end] != edit['before']:
                raise ValueError('INVALID_SOURCE_REVISION_SPAN')
            last = max(start, end - 1)
        for edit in reversed(edits):
            text = text[:edit['start']] + edit['text'] + text[edit['end']:]
        expected = sample[field]
        if field == 'question':
            expected = __import__('finarch.dataset.01-preparation.02-review.question_precision', fromlist=['align']).align(sample)[0]['question']
        if re.findall(r'\d+(?:[.,]\d+)*', text) != re.findall(r'\d+(?:[.,]\d+)*', expected):
            raise ValueError('SOURCE_REVISION_CHANGED_NUMBERS')
        revised[field] = text
    precision_module = __import__('finarch.dataset.01-preparation.02-review.question_precision', fromlist=['PATTERN'])
    if len(list(precision_module.PATTERN.finditer(sample['question']))) != len(list(precision_module.PATTERN.finditer(revised['question']))):
        raise ValueError('QUESTION_PRECISION_INSTRUCTION_REMOVED_OR_ADDED')
    remaining = __import__('finarch.dataset.01-preparation.02-review.question_precision', fromlist=['align']).align(revised)[1]
    if remaining['edits']: raise ValueError('QUESTION_PRECISION_NOT_ALIGNED')
    return revised


def revise(ctx, config, sample, audit, number):
    stage = f'02-review-and-correct/{number:02d}-round'
    response = invoke(ctx, config, stage + '/02-LLM-revise-text', '01-preparation.02-review-and-correct.revision',
                      {**{k: sample[k] for k in ('context', 'question')}, 'findings': audit.get('findings', []), **{k: sample[k] for k in ('reference_answer','reference_answer_type','reference_precision')}}, REVISION_PROMPT)
    working = apply_revision(sample, response)
    ctx.save(stage + '/03-check-revision/01-result.json', {'status': 'PASS', 'before': sample, 'after': working, 'edits': response['edits'], 'scope': 'Offsets and numeric preservation; semantic review follows'})
    original_request = __import__('finarch.dataset.01-preparation.preparation_pipeline', fromlist=['original_request']).original_request
    request = original_request(working)
    binding = {'stage16_ref': None, 'plan_sha256': None,
               'observation_sha256': observation_hash({k: working[k] for k in ('context', 'question')}),
               'checks': ['revision_spans', 'numeric_preservation']}
    audit = audit_one(ctx, config, request, binding,
                     f'02-review-and-correct/{number+1:02d}-round/01-LLM-audit-original', 'ANSWER')
    return working, audit


