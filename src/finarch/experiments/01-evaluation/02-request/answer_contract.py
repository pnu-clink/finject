"""Versioned neutral response contracts and observable consistency checks."""
import json
import math
import re
from decimal import Decimal

run_layout = __import__('finarch.experiments.90-operations.run_layout', fromlist=['*'])

TITLE = 'FinancialAnswerV5'
STABLE_TITLE = 'FinancialAnswerV6'
CLASSIFIED_TITLE = 'FinancialAnswerV7'
STRUCTURAL_TITLES = (TITLE, STABLE_TITLE, CLASSIFIED_TITLE)
CLASSIFICATIONS = ('ANSWERABLE', 'CONFLICT', 'INSUFFICIENT_EVIDENCE', 'UNRESOLVED', 'ABSTAIN')
LEGACY_DECLARATION = re.compile(
    r'^Classification: (ANSWERABLE|CONFLICT|INSUFFICIENT_EVIDENCE|UNRESOLVED); Response: (ANSWER|CONDITIONAL|ABSTAIN)\.')
BEHAVIOR_WORDS = re.compile(
    '\\babstain\\w*|\\bwithhold\\w*|\\bconflict\\w*|\\binsufficient\\b|\\bmissing information\\b|\\bconditional\\b|\\bunderdetermined\\b|\uc720\ubcf4|\ucda9\ub3cc|\uc815\ubcf4 \ubd80\uc871', re.I)


def validate_request(request):
    """AC05.1 Keep the shared schema structural and unguided solving neutral."""
    schema = request['response_schema']
    condition = run_layout.prompt_condition(request.get('prompt_condition'))
    version = schema.get('title')
    if version not in STRUCTURAL_TITLES:
        return

    def visit(value):
        if isinstance(value, dict):
            if set(value) & {'description', '$comment', 'examples', 'default'}:
                raise ValueError('V5_SCHEMA_MUST_BE_STRUCTURAL_ONLY')
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(schema)
    if 'status' in schema.get('properties', {}) or BEHAVIOR_WORDS.search(json.dumps(schema)):
        raise ValueError('V5_SCHEMA_CONTAINS_BEHAVIOR_CUE')
    if condition == 'unguided' and BEHAVIOR_WORDS.search(request['prompt']):
        raise ValueError('UNGUIDED_CONTAINS_BEHAVIOR_CUE')
    if version in (STABLE_TITLE, CLASSIFIED_TITLE):
        shared = ('For a numeric answer', '`answer_meta.negative`', '`answer_meta.scale`',
                  'answer_format.decimal_places', 'exact excerpts')
        if any(text not in request['prompt'] for text in shared):
            raise ValueError('V6_SHARED_REPRESENTATION_RULE_MISSING')
        if version == STABLE_TITLE and condition == 'guided':
            required = ('necessary information', 'conflicting facts', 'set `answer` to null',
                        'conditional', 'source', 'not assume')
            if any(text not in request['prompt'] for text in required):
                raise ValueError('V6_GUIDED_GUIDANCE_MISSING')
    if version == CLASSIFIED_TITLE:
        if (schema.get('properties', {}).get('classification') != {'type': ['string', 'null']}
                or 'classification' not in schema.get('required', [])):
            raise ValueError('CLASSIFICATION_FIELD_MUST_BE_REQUIRED_STRING_OR_NULL_WITHOUT_LABEL_CUES')
        if any(label in json.dumps(schema) for label in CLASSIFICATIONS):
            raise ValueError('CLASSIFICATION_LABELS_MUST_STAY_OUT_OF_SHARED_SCHEMA')
        if condition not in run_layout.PROMPT_FILES:
            raise ValueError('CLASSIFICATION_REQUIRES_PROMPT_CONDITION')
        if '`classification`' not in request['prompt']:
            raise ValueError('CLASSIFICATION_FIELD_GUIDANCE_MISSING')
        if condition == 'unguided' and any(label in request['prompt'] for label in CLASSIFICATIONS):
            raise ValueError('UNGUIDED_CONTAINS_CLASSIFICATION_LABELS')
        if condition == 'guided' and any(label not in request['prompt'] for label in CLASSIFICATIONS):
            raise ValueError('GUIDED_CLASSIFICATION_CRITERIA_MISSING')


def response_errors(response, request):
    """AC06.2 Check representation only, without changing raw values or meaning."""
    version = request['response_schema'].get('title')
    if version not in (STABLE_TITLE, CLASSIFIED_TITLE):
        return []
    answer, meta = response['answer'], response['answer_meta']
    errors = []

    def fail(path, message):
        errors.append({'path': path, 'rule': 'representation_consistency', 'message': message})

    if version == CLASSIFIED_TITLE:
        classification = response['classification']
        if run_layout.prompt_condition(request['prompt_condition']) == 'unguided':
            if classification is not None:
                fail(['classification'], 'Unguided solving requires a null classification.')
        elif classification not in CLASSIFICATIONS:
            fail(['classification'], 'Criteria-guided solving requires one permitted classification label.')
        elif (classification == 'ANSWERABLE') != (answer is not None):
            fail(['answer'], 'ANSWERABLE requires a number; every other classification requires null.')

    if answer is None:
        for field in ('negative', 'scale'):
            if meta[field] is not None:
                fail(['answer_meta', field], 'A null answer requires null numeric metadata.')
        return errors
    if type(answer) not in (int, float) or (type(answer) is float and not math.isfinite(answer)):
        fail(['answer'], 'A numeric answer must be a finite JSON number.')
        return errors
    if type(meta['negative']) is not bool or meta['negative'] != (answer < 0):
        fail(['answer_meta', 'negative'], 'Numeric metadata must agree with the signed answer; zero is not negative.')
    if meta['scale'] is None:
        fail(['answer_meta', 'scale'], 'A numeric answer requires its reported scale.')
    value = Decimal(str(answer)).normalize()
    if value and value.as_tuple().exponent < -request['input']['answer_format']['decimal_places']:
        fail(['answer'], 'The numeric value must be rounded to the supplied decimal_places; trailing zeros are optional.')
    return errors


def observations(response, title=TITLE):
    """AC05.3 Record numeric presence only; absence is not a semantic verdict."""
    has_number = type(response['answer']) in (int, float)
    return {
        'response_format': title,
        'numeric_answer_present': has_number,
        'answer_presence': 'NUMERIC' if has_number else 'EMPTY',
        'reported_status': None,
        'reported_classification': response.get('classification'),
        'declared_abstention': None,
        'abstention_marker_detected': None,
        'semantic_assessment': 'NOT_REVIEWED',
    }


def declaration(response):
    """Read explicit labels without translating null into an inferred judgment."""
    if not isinstance(response, dict):
        return {'classification': None, 'mode': None, 'source': None}
    if 'classification' in response:
        value = response['classification']
        return {'classification': value if isinstance(value, str) else None,
                'mode': None, 'source': 'JSON_FIELD'}
    explanation = response.get('explanation')
    match = LEGACY_DECLARATION.match(explanation) if isinstance(explanation, str) else None
    return {'classification': match[1] if match else None,
            'mode': match[2] if match else None,
            'source': 'LEGACY_EXPLANATION_PREFIX' if match else None}
