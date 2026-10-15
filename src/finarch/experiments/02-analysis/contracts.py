"""Structural contracts for recorded analysis; never judge question validity."""
from jsonschema import Draft202012Validator
from copy import deepcopy
from finarch.experiments import assets

INTERPRETATIONS = assets.schema('interpretations')
INTERPRETATION_RESPONSE = assets.schema('comparison_response')
FINDINGS = assets.schema('research_response')
CATEGORIES = INTERPRETATIONS['items']['properties']['category']['enum']


def validate_response(value, request):
    """Check structure and traceability, not whether a question is answerable."""
    try:
        Draft202012Validator(request['response_schema']).validate(value)
        if request['stage'] == '02_comparison':
            observed = request['input']['responses']
            if value['observations']:
                validate_interpretations(value['observations'], {r['response_id']: r for r in observed})
            elif 'response_assessments' not in request['response_schema']['properties'] and any(r.get('response') for r in observed):
                raise ValueError('OBSERVATIONS_REQUIRED_FOR_RETURNED_RESPONSES')
            if 'response_assessments' in request['response_schema']['properties']:
                if not value['coverage_note'].strip():
                    raise ValueError('COVERAGE_NOTE_REQUIRED')
                validate_assessments(value['response_assessments'], request)
        elif request['stage'] == '04_quadrant':
            grouping = __import__('finarch.experiments.02-analysis.04-quadrant.01-findings.grouping', fromlist=['*'])
            grouping.validate(value, request)
        else:
            if value['run'] != request['input']['run']:
                raise ValueError('FINDINGS_RUN_MISMATCH')
            validate_findings(value, request['input']['interpretations'])
        return []
    except Exception as error:
        return [{'path': '', 'rule': 'ANALYSIS_CONTRACT', 'message': str(error)[:2000]}]


def validate_interpretations(value, rows):
    # Frozen V1 observations retain their original language field and schema.
    for item in value:
        schema = deepcopy(INTERPRETATIONS['items'])
        if 'display_ko' in item and 'display' not in item:
            schema['properties']['display_ko'] = schema['properties'].pop('display')
            schema['required'] = ['display_ko' if k == 'display' else k for k in schema['required']]
        Draft202012Validator(schema).validate(item)
    seen = set()
    for item in value:
        if item['id'] in seen:
            raise ValueError('DUPLICATE_INTERPRETATION')
        seen.add(item['id'])
        for ref in item['response_ids']:
            if ref not in rows:
                raise ValueError('UNKNOWN_RESPONSE_REFERENCE:' + ref)
        for excerpt in item['excerpts']:
            if excerpt['response_id'] not in item['response_ids']:
                raise ValueError('EXCERPT_OUTSIDE_OBSERVATION')
            response = rows[excerpt['response_id']]['response'] or {}
            source = response.get(excerpt['field'], '')
            strings = source if isinstance(source, list) else [source]
            if not any(isinstance(s, str) and excerpt['quote'] in s for s in strings):
                raise ValueError('EXCERPT_NOT_IN_SAVED_RESPONSE')
    return True


def review_status(row, request):
    if row.get('status') != 'VALID' or not isinstance(row.get('response'), dict):
        return 'NOT_REVIEWABLE'
    public = request['input']['inputs'].get(row['item_id'], {}).get('public', {})
    if any(not isinstance(public.get(k), str) or not public[k].strip() for k in ('question', 'context')):
        return 'SOURCE_MISSING'
    return 'COMPLETED'


def validate_assessments(assessments, request):
    """Check coverage, applicability and verbatim citations, not semantic truth."""
    rows = {r['response_id']: r for r in request['input']['responses'] if r['variant'] != 'ORIGINAL'}
    ids = [a['response_id'] for a in assessments]
    if len(ids) != len(set(ids)) or set(ids) != set(rows):
        raise ValueError('ASSESSMENT_COVERAGE_MISMATCH')
    for assessment in assessments:
        row = rows[assessment['response_id']]
        status = review_status(row, request)
        if assessment['review_status'] != status:
            raise ValueError('ASSESSMENT_REVIEW_STATUS_MISMATCH')
        public = request['input']['inputs'].get(row['item_id'], {}).get('public', {})
        response = row.get('response') or {}
        for key in ('abstention_reason_validity', 'decision_grounding'):
            judgment = assessment[key]
            verdict = judgment['verdict']
            if status != 'COMPLETED':
                if verdict is not None or judgment['citations']:
                    raise ValueError('UNREVIEWABLE_ASSESSMENT_HAS_VERDICT_OR_CITATION')
                continue
            allowed = {'SUPPORTED', 'UNSUPPORTED', 'UNDETERMINED'}
            if key == 'abstention_reason_validity' and response.get('answer') is not None:
                allowed = {'NOT_APPLICABLE'}
            if verdict not in allowed:
                raise ValueError('ASSESSMENT_VERDICT_NOT_APPLICABLE')
            sources = set()
            for citation in judgment['citations']:
                source, index = citation['source'], citation['evidence_index']
                if source == 'evidence':
                    evidence = response.get('evidence', [])
                    if type(index) is not int or not isinstance(evidence, list) or not 0 <= index < len(evidence):
                        raise ValueError('ASSESSMENT_EVIDENCE_INDEX_INVALID')
                    text = evidence[index]
                else:
                    if index is not None:
                        raise ValueError('ASSESSMENT_UNEXPECTED_EVIDENCE_INDEX')
                    text = (public if source in ('question', 'context') else response).get(source)
                if not isinstance(text, str) or citation['quote'] not in text:
                    raise ValueError('ASSESSMENT_QUOTE_NOT_IN_SOURCE')
                sources.add(source)
            if verdict != 'NOT_APPLICABLE' and (not sources & {'question', 'context'} or not sources & {'explanation', 'evidence'}):
                raise ValueError('ASSESSMENT_INPUT_AND_RESPONSE_CITATIONS_REQUIRED')
    return True


def collect_assessments(root, requests, backend):
    from importlib import import_module
    return import_module('finarch.experiments.02-analysis.02-comparison.response_assessments').collect(root, requests, backend)


def validate_findings(value, interpretations):
    Draft202012Validator(FINDINGS).validate(value)
    known = {r['id'] for r in interpretations}
    ids = [r['id'] for r in value['findings']]
    if len(ids) != len(set(ids)):
        raise ValueError('DUPLICATE_FINDING')
    if any(ref not in known for f in value['findings'] for ref in f['interpretation_ids']):
        raise ValueError('UNKNOWN_INTERPRETATION_REFERENCE')
    return True
