"""Record an LLM-only inverse judgment without changing the EA quality verdict."""
from datetime import datetime, timezone
from importlib import import_module
import hashlib
import json
from pathlib import Path

from finarch.dataset.schemas.ea_inverse_review import ROLE
from finarch.dataset.schemas.registry import canonical, require_llm_schema
from finarch.dataset.schemas.validation import validate
from finarch.shared.providers.cli import call, prepare_instruction, read_settings

StepStopped = import_module('finarch.dataset.90-operations.staging').StepStopped
write = import_module('finarch.dataset.90-operations.preparation_gate').write
TEMPLATE = Path(__file__).parents[3]/'documentation/templates/ea-inverse-review.md'
BASE = '03-validation/07-ea-inverse-review'


def evidence_display_check(qc, evidence):
    """Resolve quotations for display only; never solve equations or alter judgments."""
    checks, resolved = [], []
    for index, item in enumerate(evidence):
        text = qc[item['field']]
        start, end, quote = item['start'], item['end'], item['quote']
        if 0 <= start < end <= len(text) and text[start:end] == quote:
            status = 'EXACT_OFFSETS'
        else:
            first = text.find(quote)
            if first >= 0 and text.find(quote, first+1) < 0:
                start, end, status = first, first+len(quote), 'UNIQUE_QUOTE_MATCH'
            else:
                status = 'AMBIGUOUS_QUOTE' if first >= 0 else 'QUOTE_NOT_FOUND'
        check = {'index': index, 'status': status, 'original': item}
        if status in ('EXACT_OFFSETS', 'UNIQUE_QUOTE_MATCH'):
            span = {'field': item['field'], 'start': start, 'end': end, 'quote': quote}
            resolved.append(span)
            check['resolved'] = span
        checks.append(check)
    return {'status': 'WARNING' if len(resolved) != len(evidence) else 'PASS',
            'checks': checks, 'resolved_evidence': resolved,
            'scope': 'Display coordinates only; no formula or recovery verification.'}


def _reserve_attempt(ctx):
    for number in range(1, 10000):
        stage = f'{BASE}/attempt-{number:03d}'
        try:
            (ctx.root/stage).mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            continue
        return stage
    raise ValueError('EA_INVERSE_ATTEMPT_LIMIT')


def review(ctx, config, observation, *, private_ref=None, local=None, profile_id=None):
    """Send exactly final Q/C in a fresh call; persist an immutable annotation."""
    qc = {key: observation[key] for key in ('question', 'context')}
    stage = _reserve_attempt(ctx)
    qc_hash = hashlib.sha256(canonical(qc)).hexdigest()
    ctx.save(stage+'/01-input/qc.json', qc)
    # Linkage is private and is never merged into the model request.
    ctx.save(stage+'/01-input/private.ref.json', private_ref or {})
    record = {'kind': 'EA_INVERSE_REVIEW', 'version': 1, 'status': 'NOT_RUN',
              'role': ROLE, 'timestamp': datetime.now(timezone.utc).isoformat(),
              'observation_sha256': qc_hash, 'inverse_review': None,
              'request_ref': stage+'/01-input/qc.json',
              'affects_quality_status': False, 'automatic_retries': 0,
              'scope': 'LLM annotation from remaining Q/C; not a proof or an EA rejection.'}
    display = {'status': 'NOT_RUN', 'checks': [], 'resolved_evidence': []}
    ready = False
    try:
        definition = require_llm_schema(ROLE)
        require_llm_schema(ROLE, 'request')
        validate(ROLE+'.request', qc)
        instruction, prompt = prepare_instruction(ROLE, qc)
        ctx.save_text(stage+'/01-input/prompt.md', instruction)
        ctx.save(stage+'/01-input/prompt-selection.json', prompt)
        ctx.save(stage+'/01-input/response-schema.json', definition)
        if local is None:
            settings = read_settings(config, ROLE, profile_id=profile_id)
            record['model'] = {key: settings[key] for key in ('provider', 'model', 'effort', 'profile')}
            # Pin the resolved profile so the recorded model and actual call agree.
            resolved_profile_id = settings['profile']['id'] if settings['profile'] else profile_id
            local = lambda payload, response_schema: call(
                config, ROLE, payload, profile_id=resolved_profile_id,
                save=lambda name, value: ctx.save(stage+'/02-call/'+name, value))
        else:
            record['model'] = {'provider': 'injected-test-handler'}
        ready = True
        value = ctx.invoke(stage, '02-call', ROLE, qc, local=local)
        # RunContext already validates it; this also guards alternate contexts.
        validate(ROLE+'.response', value)
        record.update(status='COMPLETED', inverse_review=value['inverse_review'])
        display = evidence_display_check(qc, value['inverse_review']['evidence'])
    except StepStopped as error:
        reason = error.result.reason
        invalid = reason in ('RESPONSE_JSON_INVALID', 'RESPONSE_SCHEMA_INVALID')
        record.update(status='RESPONSE_INVALID' if invalid else 'CALL_FAILED', reason=reason)
    except Exception as error:
        # Do not expose arbitrary transport errors or turn absence into false.
        record.update(status='RESPONSE_INVALID' if ready else 'NOT_RUN',
                      reason='EA_INVERSE_'+type(error).__name__)
        ctx.save(stage+'/03-result/preflight-or-handler-check.json', {
            'status': 'FAIL', 'phase': 'after_handler' if ready else 'before_call',
            'reason': getattr(error, 'reason', record['reason']), 'error_type': type(error).__name__})
    record['evidence_display_check_ref'] = stage+'/03-result/evidence-display-check.json'
    ctx.save(record['evidence_display_check_ref'], display)
    path = stage+'/03-result/inverse-review.json'
    ctx.save(path, record)
    ctx.save_text(stage+'/README.md', TEMPLATE.read_text().format(
        status=record['status'], role=ROLE, observation_sha256=qc_hash))
    ref = {'path': path, 'sha256': hashlib.sha256((ctx.root/path).read_bytes()).hexdigest(),
           'observation_sha256': qc_hash, 'version': 1}
    # A worker only publishes within its own variant; run-wide files stay with the scheduler.
    write(ctx.root/BASE/'latest.ref.json', ref)
    ctx.trace.artifact(BASE+'/latest.ref.json', ref)
    return ref


def verify_reference(root, ref, observation):
    """Reject stale or tampered annotation links without interpreting their boolean."""
    root = Path(root).resolve()
    path = (root/ref['path']).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('EA_INVERSE_REFERENCE_OUTSIDE_VARIANT')
    if hashlib.sha256(path.read_bytes()).hexdigest() != ref['sha256']:
        raise ValueError('EA_INVERSE_REFERENCE_HASH_MISMATCH')
    qc = {key: observation[key] for key in ('question', 'context')}
    record = json.loads(path.read_text())
    expected = hashlib.sha256(canonical(qc)).hexdigest()
    if ref['observation_sha256'] != expected or record['observation_sha256'] != expected:
        raise ValueError('EA_INVERSE_OBSERVATION_MISMATCH')
    return record
