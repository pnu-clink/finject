"""Summarize confirmed external use from one saved Preparation round."""
import hashlib
import json
import re
from pathlib import Path


EXTERNAL_TYPES = ('EXTERNAL_RULE', 'EXTERNAL_DATA')


def _source(run, path, references):
    if not path.is_file() or path.is_symlink():
        return None
    relative = str(path.relative_to(run))
    raw = path.read_bytes()
    references[relative] = hashlib.sha256(raw).hexdigest()
    return json.loads(raw)


def classify(run, row):
    """Return the two-field private label and the evidence used to derive it.

    False means the *confirmed-use gate* was not met, not proof of non-use.
    """
    run = Path(run).resolve()
    case, round_name = row['id'], row.get('round')
    if not re.fullmatch(r'test-[0-9]+', case) or (round_name is not None and
            not re.fullmatch(r'[0-9]+-round', round_name)):
        raise ValueError('INVALID_EXTERNAL_KNOWLEDGE_CASE_OR_ROUND:' + case)
    references = {}
    state = _source(run, run / '01-preparation' / case / 'run.json', references) or {'status': 'NOT_RUN'}
    if (state.get('status') != row['status'] or state.get('active_round') != round_name):
        raise ValueError('EXTERNAL_KNOWLEDGE_STATUS_DRIFT:' + case)
    negative = {'used': False, 'used_types': []}
    if row['status'] != 'PASS':
        return negative, {'reason': 'PREPARATION_NOT_PASS', 'sources': references}
    if not round_name:
        raise ValueError('EXTERNAL_KNOWLEDGE_PASS_WITHOUT_ROUND:' + case)
    base = run / '01-preparation' / case / round_name
    paths = {
        'program': '03-calculation/05-record-calculation-artifacts/03-program.json',
        'calculation': '03-calculation/05-record-calculation-artifacts/01-stage-output.json',
        'answer_trace': '04-graph/04-trace-answer-dependencies/01-result.json',
        'verification_input': '05-verification/05-build-verification-request/01-input.json',
        'verdict': '05-verification/08-record-verdict/01-result.json',
    }
    values = {name: _source(run, base / relative, references) for name, relative in paths.items()}
    if any(value is None for value in values.values()):
        raise ValueError('EXTERNAL_KNOWLEDGE_PASS_EVIDENCE_MISSING:' + case)
    sample = row['input']
    for name, actual in (('calculation', values['calculation'].get('sample', {})),
                         ('verification_input', values['verification_input'].get('sample', {}))):
        if any(sample.get(field) != actual.get(field) for field in ('question', 'context')):
            raise ValueError(f'EXTERNAL_KNOWLEDGE_QC_MISMATCH:{case}:{name}')
    program = values['program']
    if program != values['calculation'].get('program'):
        raise ValueError('EXTERNAL_KNOWLEDGE_PROGRAM_MISMATCH:' + case)
    declared = set(program.get('calculation_input_sources') or [])
    usages = program.get('source_usage') or []
    if declared != {usage.get('kind') for usage in usages}:
        raise ValueError('EXTERNAL_KNOWLEDGE_PROGRAM_TYPES_MISMATCH:' + case)
    trace = values['answer_trace']
    trace_usages = trace.get('source_usage') or []
    traced = set(trace.get('calculation_input_sources') or [])
    if traced != {usage.get('kind') for usage in trace_usages} or not traced <= declared:
        raise ValueError('EXTERNAL_KNOWLEDGE_TRACE_TYPES_MISMATCH:' + case)
    # UNAVAILABLE declares a missing dependency; it is not information used.
    used = {usage['kind'] for usage in trace_usages if usage.get('kind') in EXTERNAL_TYPES
            and usage.get('acquisition') != 'UNAVAILABLE'}
    verdict = values['verdict']
    if verdict.get('status') != 'PASS' or verdict.get('cohort') != 'EXTERNAL':
        return negative, {'reason': 'VERIFICATION_NOT_EXTERNAL_PASS', 'sources': references}
    required = set(verdict.get('required_external_sources') or [])
    confirmed = [kind for kind in EXTERNAL_TYPES if kind in used and kind in required]
    if not confirmed:
        return negative, {'reason': 'NO_USED_AND_REQUIRED_TYPE', 'sources': references}
    return {'used': True, 'used_types': confirmed}, {'reason': 'CONFIRMED', 'sources': references}
