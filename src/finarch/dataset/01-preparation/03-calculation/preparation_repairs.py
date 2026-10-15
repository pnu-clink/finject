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


REVISION_PROMPT = read_prompt('01-preparation.03-calculation.source-revision.md')

EVIDENCE_PROMPT = read_prompt('01-preparation.03-calculation.review-answer-evidence.md')


def invoke(ctx, config, stage, role, request, instruction):
    def handler(payload, *, response_schema):
        return call(config, role, payload, instruction=instruction,
                    save=lambda name, value: ctx.save(stage + '/03-LLM-call/' + name, value))
    return ctx.invoke(stage, '01-request', role, request, local=handler)


def resolve_mismatch(ctx, config, sample, program, execution, stage='03-calculation/05-resolve-mismatch', independent_source=None, evidence_source=None):
    request = {k: sample[k] for k in ('context', 'question')}
    request.update({key: sample[key] for key in ('reference_answer_type', 'reference_precision')})
    request['answer_metadata'] = {key: sample['answer_metadata'][key] for key in ('scale', 'negative')}
    numeric_index = import_module('finarch.dataset.shared.calculation.numeric_index').numeric_index
    request['provider_record'] = {'numeric_index': numeric_index(sample['context'])}
    prompt = read_prompt('01-preparation.03-calculation.pot.md')
    prompt += read_prompt('01-preparation.03-calculation.independent-solve.md')
    if independent_source is None:
        response = invoke(ctx, config, stage + '/01-LLM-solve-independently', '01-preparation.03-calculation.pot', request, prompt)
        independent, layout = name_constants(executable_program(response))
        result = ctx.invoke(stage, '02-execute-independent', 'pot.execute', {**independent, 'context': sample['context']},
                            local=lambda value: execute(value, save=lambda name, data: ctx.save(stage + '/02-execute-independent/details/' + name, data)))
    else:
        import json
        source=Path(independent_source).resolve()
        if not source.is_relative_to(ctx.root.resolve()):raise ValueError('INDEPENDENT_SOURCE_OUTSIDE_CASE')
        payload=json.loads((source/'02-execute-independent/01-input.json').read_text())
        if payload['context']!=sample['context']:raise ValueError('INDEPENDENT_CONTEXT_CHANGED')
        independent={k:v for k,v in payload.items() if k!='context'}
        ctx.save(stage+'/00-independent-source.json',{'path':str(source.relative_to(ctx.root)),'new_model_call':False})
        result=ctx.invoke(stage,'02-execute-independent','pot.execute',payload,local=lambda value:execute(value))
    comparison = compare(result['exact_value'], Reference(sample['reference_answer'], sample['reference_answer_type'], sample['reference_precision']))
    ctx.save(stage + '/02-compare-solutions/01-result.json', {'gold': sample['reference_answer'], 'pot': execution['exact_value'], 'independent': result['exact_value'], 'independent_gold': comparison})
    if evidence_source is None:
        review = invoke(ctx, config, stage + '/03-LLM-review-evidence', '01-preparation.03-calculation.review-answer-evidence',
                        {**{k: sample[k] for k in ('context', 'question')}, 'original_program': program, 'independent_program': independent,
                         'original_result': str(execution['exact_value']), 'independent_result': str(result['exact_value']),
                         'gold': str(sample['reference_answer'])}, EVIDENCE_PROMPT)
    else:
        import json
        from finarch.dataset.schemas.preparation import EvidenceResponse
        source=Path(evidence_source).resolve()
        if not source.is_relative_to(ctx.root.resolve()):raise ValueError('EVIDENCE_SOURCE_OUTSIDE_CASE')
        review=EvidenceResponse.model_validate(json.loads(source.read_text())['data']).model_dump()
        ctx.save(stage+'/03-evidence-source.json',{'path':str(source.relative_to(ctx.root)),'new_model_call':False})
    citation_checks=[]
    for evidence in review['evidence']:
        original=evidence['quote'];quote=original
        if quote not in sample[evidence['field']]:
            quote=quote.replace('\\n','\n').replace('\\t','\t')
        if quote not in sample[evidence['field']]:raise ValueError('UNGROUNDED_MISMATCH_EVIDENCE')
        citation_checks.append({'original_quote':original,'matched_quote':quote,'field':evidence['field'],'escaped_whitespace_decoded':original!=quote})
    ctx.save(stage+'/03-citation-check.json',{'status':'PASS','citations':citation_checks})
    working = copy.deepcopy(sample)
    if review['conclusion'] == 'POT_ERROR' and comparison['matches']:
        corrected, corrected_result = independent, result
    elif review['conclusion'] == 'GOLD_ERROR' and comparison['computed'] == compare(execution['exact_value'], Reference(sample['reference_answer'], sample['reference_answer_type'], sample['reference_precision']))['computed']:
        corrected, corrected_result = program, execution
        working['reference_answer'] = normalize(result['exact_value'], Reference(sample['reference_answer'], sample['reference_answer_type'], sample['reference_precision']))
    else:
        raise ValueError('MISMATCH_REQUIRES_HUMAN_RESOLUTION')
    ctx.save(stage + '/04-apply-correction/01-result.json', {'original_input': sample, 'working_input': working,
             'program': corrected, 'evidence_review': review, 'requires_human_approval': True})
    confirmed = ctx.invoke(stage, '05-execute-and-compare', 'pot.execute', {**corrected, 'context': working['context']},
                           local=lambda value: execute(value, save=lambda name, data: ctx.save(stage + '/05-execute-and-compare/details/' + name, data)))
    matched = compare(confirmed['exact_value'], Reference(working['reference_answer'], working['reference_answer_type'], working['reference_precision']))
    if not matched['matches']:
        raise ValueError('CORRECTION_REEXECUTION_MISMATCH')
    return working, corrected, confirmed, matched
