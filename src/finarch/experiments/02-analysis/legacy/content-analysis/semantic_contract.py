"""Frozen schemas and local gates for blinded input and response assessment."""
from jsonschema import Draft202012Validator

STATES = ['ANSWERABLE', 'CONFLICT', 'INSUFFICIENT_EVIDENCE', 'UNRESOLVED']
OUTCOMES = ['SUPPORTED_ANSWER', 'SUPPORTED_CONDITIONAL_OR_ABSTENTION',
            'UNJUSTIFIED_ABSTENTION', 'UNSUPPORTED_ANSWER',
            'CALCULATION_OR_REASONING_ERROR', 'EVIDENCE_ERROR', 'UNRESOLVED']
DIMENSIONS = ['PASS', 'FAIL', 'NOT_APPLICABLE', 'UNRESOLVED']


def obj(properties):
    return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}


def string(nullable=False):
    return {'type': ['string', 'null'] if nullable else 'string'}


def array(items):
    return {'type': 'array', 'items': items}


def enum(values):
    return {'type': 'string', 'enum': values}


QUOTE = obj({'source': enum(['question', 'context']), 'quote': string()})
INPUT_SCHEMA = obj({
    'classification': enum(STATES), 'justified_answer': {'type': ['number', 'null']},
    'conditional_answers': array(obj({'condition': string(), 'answer': {'type': 'number'}, 'unit_scale': string()})),
    'reasoning': string(), 'evidence': array(QUOTE), 'external_rules': array(string()),
    'requires_external_data': {'type': 'boolean'},
    'confidence': enum(['HIGH', 'MEDIUM', 'LOW']), 'unresolved_reason': string(True),
})
REVIEW = obj({
    'response_id': string(), 'behavior': enum(['ANSWER', 'CONDITIONAL', 'ABSTAIN', 'UNINTERPRETABLE']),
    'outcome': enum(OUTCOMES), 'calculation': enum(DIMENSIONS), 'grounding': enum(DIMENSIONS),
    'consistency': enum(DIMENSIONS), 'classification_agreement': enum(['AGREE', 'DISAGREE', 'NOT_STATED', 'UNRESOLVED']),
    'model_stated_reason': string(True), 'reasoning': string(), 'qc_evidence': array(QUOTE),
    'response_evidence': array(string()), 'response_would_change_input_assessment': string(True),
})
RESPONSE_SCHEMA = obj({'reviews': array(REVIEW)})
RESEARCH_SCHEMA = obj({
    'overall_assessment': string(),
    'findings': array(obj({'title': string(), 'observation': string(),
                           'evidence_trial_ids': array(string()), 'alternative_explanation': string(),
                           'limitation': string()})),
    'recommendations': array(obj({'priority': enum(['HIGH', 'MEDIUM', 'LOW']), 'proposal': string(),
                                  'reason': string(), 'evidence_trial_ids': array(string()),
                                  'smallest_check': string()})),
    'unresolved_questions': array(string()),
    'paper_claims_not_supported': array(string()),
})


def validate(value, request):
    errors = [{'path': list(e.path), 'message': e.message} for e in Draft202012Validator(request['response_schema']).iter_errors(value)]
    if errors:
        return errors
    data = request['input']

    def fail(message):
        errors.append({'message': message})

    def quotes(entries):
        for entry in entries:
            if not entry['quote'] or entry['quote'] not in data[entry['source']]:
                fail('JUDGE_QUOTE_NOT_EXACT_SUBSTRING')

    if request['stage'] == 'research':
        allowed = {row['trial_id'] for row in data['evidence']}
        if not value['overall_assessment'].strip() or not value['findings'] or not value['paper_claims_not_supported']:
            fail('RESEARCH_REQUIRES_FINDINGS_AND_LIMITATIONS')
        for finding in value['findings']:
            if not finding['evidence_trial_ids']:
                fail('RESEARCH_FINDING_REQUIRES_SAVED_EVIDENCE')
        for row in [*value['findings'], *value['recommendations']]:
            if set(row['evidence_trial_ids']) - allowed:
                fail('RESEARCH_REFERENCES_UNSUPPLIED_TRIAL')
    elif request['stage'] == 'input':
        quotes(value['evidence'])
        if not value['reasoning'].strip() or not value['evidence']:
            fail('INPUT_ASSESSMENT_REQUIRES_REASON_AND_EVIDENCE')
        if (value['classification'] == 'ANSWERABLE') != (type(value['justified_answer']) in (int, float)):
            fail('INPUT_CLASS_AND_ANSWER_INCONSISTENT')
        if value['classification'] == 'UNRESOLVED' and not value['unresolved_reason']:
            fail('UNRESOLVED_REQUIRES_REASON')
    else:
        expected = {r['response_id']: r['response'] for r in data['responses']}
        ids = [r['response_id'] for r in value['reviews']]
        if len(ids) != len(set(ids)) or set(ids) != set(expected):
            fail('JUDGE_RESPONSE_ID_SET_MISMATCH')
            return errors
        for review in value['reviews']:
            quotes(review['qc_evidence'])
            response = expected[review['response_id']]
            texts = [response.get('explanation', ''), *response.get('evidence', [])]
            for quote in review['response_evidence']:
                if not quote or not any(quote in text for text in texts):
                    fail('JUDGE_RESPONSE_QUOTE_NOT_EXACT_SUBSTRING')
            stated = review['model_stated_reason']
            if stated is not None and (not stated or stated not in response.get('explanation', '')):
                fail('MODEL_STATED_REASON_NOT_ACTUALLY_STATED')
            if not review['reasoning'].strip() or not review['qc_evidence']:
                fail('REVIEW_REQUIRES_REASON_AND_INPUT_EVIDENCE')
            if review['response_would_change_input_assessment'] and review['outcome'] != 'UNRESOLVED':
                fail('INPUT_ASSESSMENT_CHALLENGE_REQUIRES_ADJUDICATION')
            if review['outcome'].startswith('SUPPORTED_') and any(review[k] in ('FAIL', 'UNRESOLVED') for k in ('calculation', 'grounding', 'consistency')):
                fail('SUPPORTED_REVIEW_CONTRADICTS_DIMENSIONS')
    return errors
