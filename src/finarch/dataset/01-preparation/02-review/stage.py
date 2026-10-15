"""Review source once per outer round, preserving constrained corrections."""
from importlib import import_module
from finarch.shared.providers.cli import call
from finarch.dataset.shared.prompts import read_prompt

ROLE = '01-preparation.02-review-and-correct.revision'


def original_request(sample):
    return {'original_context': sample['context'], 'context': sample['context'],
            'question': sample['question'], 'axis': 'ANSWER',
            'intent': {'preserve_original': True, 'align_question_precision_to_reference': True},
            **{k: sample[k] for k in ('reference_answer', 'reference_answer_type', 'reference_precision')},
            'edits': [], 'recovery_review': 'DEFERRED_BY_USER'}


def run(ctx, config, sample, maximum=0):
    request = pp01_read_input(ctx, sample)
    response = pp02_LLM_review_original(ctx, config, request)
    return pp03_record_result(ctx, sample, response)


def pp01_read_input(ctx, sample):
    precision = import_module('finarch.dataset.01-preparation.02-review.question_precision')
    _, check = precision.align(sample)
    ctx.save('02-review/00-question-precision/01-check.json', check)
    request = {key: sample[key] for key in ('context', 'question', 'reference_answer',
                                          'reference_answer_type', 'reference_precision')}
    request['findings'] = check['edits']
    ctx.save('02-review/01-read-input/01-input.json', request)
    return request


def pp02_LLM_review_original(ctx, config, request):
    def review(payload, *, response_schema):
        return call(config, ROLE, payload,
            instruction=read_prompt('01-preparation.02-review-and-correct.revision.md'),
            save=lambda name, value: ctx.save('02-review/02-LLM-review-original/'+name, value))
    return ctx.invoke('02-review', '02-LLM-review-original', ROLE, request, local=review)


def pp03_record_result(ctx, sample, response):
    revisions = import_module('finarch.dataset.01-preparation.02-review.revisions')
    working = sample
    if response['disposition'] == 'REVISED':
        working = revisions.apply_revision(sample, response)
    elif response['edits']:
        raise ValueError('SOURCE_REVIEW_DISPOSITION_CONFLICT')
    precision = import_module('finarch.dataset.01-preparation.02-review.question_precision')
    unresolved = response['disposition'] == 'AMBIGUOUS' or bool(precision.align(working)[1]['edits'])
    audit = {'status': 'FAIL' if unresolved else 'PASS', 'reason': response['reason'],
             'findings': response['edits'], 'disposition': response['disposition']}
    ctx.save('02-review/03-record-result/01-result.json',
             {'before': sample, 'after': working, 'edits': response['edits'], 'audit': audit})
    return working, audit
