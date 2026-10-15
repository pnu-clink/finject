"""Current numeric answers and preserved magnitude contracts."""
import math
import re
from decimal import Decimal

from jsonschema import Draft202012Validator
answer_contract = __import__('finarch.experiments.01-evaluation.02-request.answer_contract', fromlist=['*'])

TITLE = 'FinancialAnswerMagnitudeV4'
LEGACY_TITLE = 'FinancialAnswerMagnitudeV3'


def is_numeric(schema):
    return schema.get('title') in (TITLE, LEGACY_TITLE, *answer_contract.STRUCTURAL_TITLES)


def metadata(response):
    """Read the current nested contract or a preserved flat V3 response."""
    return response['answer_meta'] if 'answer_meta' in response else response


def model_input(public, schema):
    """Read the complete public payload; never supplement it from private data."""
    if set(public) - {'item_id', 'question', 'context', 'answer_format'}:
        raise ValueError('PRIVATE_FIELDS_IN_PUBLIC_INPUT')
    result = {key: public[key] for key in ('question', 'context')}
    if not all(isinstance(value, str) and value.strip() for value in result.values()):
        raise ValueError('EMPTY_OR_INVALID_QUESTION_CONTEXT')
    if is_numeric(schema):
        if 'answer_format' not in public:
            raise ValueError('PUBLIC_ANSWER_FORMAT_REQUIRED_REPREPARE_FROM_DATASET')
        meta = public['answer_format']
        if not isinstance(meta, dict) or set(meta) != {'decimal_places'}:
            raise ValueError('INVALID_OR_PRIVATE_ANSWER_FORMAT_FIELDS')
        if type(meta['decimal_places']) is not int or not 0 <= meta['decimal_places'] <= 100:
            raise ValueError('INVALID_DECIMAL_PLACES')
        result['answer_format'] = dict(meta)
    elif 'answer_format' in public:
        raise ValueError('PUBLIC_PAYLOAD_CONTRACT_MISMATCH')
    return result


def validate_input(request):
    answer_contract.validate_request(request)
    expected = {'question', 'context'}
    if is_numeric(request['response_schema']):
        expected.add('answer_format')
    payload = request['input']
    if set(payload) != expected:
        raise ValueError('PRIVATE_OR_MISSING_FIELDS_IN_MODEL_INPUT')
    if 'answer_format' in expected:
        meta = payload['answer_format']
        if not isinstance(meta, dict) or set(meta) != {'decimal_places'}:
            raise ValueError('INVALID_OR_PRIVATE_ANSWER_FORMAT_FIELDS')
        digits = meta['decimal_places']
        if type(digits) is not int or not 0 <= digits <= 100:
            raise ValueError('INVALID_DECIMAL_PLACES')


def response_errors(response, request):
    errors = [{'path': list(e.absolute_path), 'rule': e.validator, 'message': e.message[:250]}
              for e in Draft202012Validator(request['response_schema']).iter_errors(response)]
    if errors or not is_numeric(request['response_schema']):
        return errors

    if request['response_schema'].get('title') in answer_contract.STRUCTURAL_TITLES:
        answer = response['answer']
        if type(answer) is float and not math.isfinite(answer):
            errors.append({'path': ['answer'], 'rule': 'type', 'message': 'JSON numbers must be finite.'})
        return errors + answer_contract.response_errors(response, request)

    meta = metadata(response)

    def fail(path, message):
        location = ['answer_meta', path] if path == 'negative' and 'answer_meta' in response else [path]
        errors.append({'path': location, 'rule': 'answer_format', 'message': message})

    if response['status'] == 'abstained':
        if response['answer'] is not None:
            fail('answer', 'Abstention requires a null answer.')
        if meta['negative'] is not None:
            fail('negative', 'Abstention requires a null sign.')
        return errors
    answer = response['answer']
    if not isinstance(answer, str):
        fail('answer', 'An answered response requires an unsigned numeric string.')
        return errors
    digits = request['input']['answer_format']['decimal_places']
    pattern = r'(?:0|[1-9][0-9]*)' + (rf'\.[0-9]{{{digits}}}' if digits else '')
    if not re.fullmatch(pattern, answer):
        fail('answer', f'Use an unsigned decimal string with exactly {digits} decimal places; no symbols or separators.')
    if type(meta['negative']) is not bool:
        fail('negative', 'An answered response requires a boolean sign.')
    if not errors and Decimal(answer) == 0 and meta['negative']:
        fail('negative', 'A rounded zero must have negative=false.')
    return errors


def compare_answer(response, reference):
    signed = Decimal(str(response['answer']))
    if 'status' in response:
        signed = signed.copy_negate() if metadata(response)['negative'] else signed
    gold = Decimal(reference['reference_answer'])
    # The model already reports the requested precision. Do not truncate or rescale it again.
    matches = signed == gold
    return {'computed': format(signed, 'f'), 'gold': format(gold, 'f'),
            'exact_value': format(signed, 'f'), 'matches': matches,
            'exact_matches': matches, 'normalized_matches': matches,
            'policy': 'DIRECT_SIGNED_DECIMAL_IN_QUESTION_SCALE', **reference}
