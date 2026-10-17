"""Recorded Responses usage and auditable, response-deduplicated run summaries.

CLI: python -m finarch.shared.run_logging.api_usage --run reports/run/<run-id>
No requests, credentials or model execution are used by this module.
"""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path

PRICING = Path(__file__).with_name('api-pricing-snapshot.json')
TOKEN_FIELDS = ('input_tokens', 'cached_input_tokens', 'cache_write_tokens',
                'output_tokens', 'reasoning_tokens', 'total_tokens')


def pricing_snapshot():
    raw = PRICING.read_bytes()
    return {**json.loads(raw), 'snapshot_sha256': hashlib.sha256(raw).hexdigest()}


def _count(value):
    return value if type(value) is int and value >= 0 else None


def normalize_usage(raw):
    raw = raw if isinstance(raw, dict) else {}
    inputs = raw.get('input_tokens_details') or {}
    outputs = raw.get('output_tokens_details') or {}
    result = {
        'input_tokens': _count(raw.get('input_tokens')),
        'cached_input_tokens': _count(inputs.get('cached_tokens')),
        'cache_write_tokens': _count(inputs.get('cache_write_tokens')),
        'output_tokens': _count(raw.get('output_tokens')),
        'reasoning_tokens': _count(outputs.get('reasoning_tokens')),
        'reported_total_tokens': _count(raw.get('total_tokens')),
    }
    i, o = result['input_tokens'], result['output_tokens']
    result['total_tokens'] = i + o if i is not None and o is not None else None
    result['total_matches_reported'] = (None if result['reported_total_tokens'] is None or
        result['total_tokens'] is None else result['reported_total_tokens'] == result['total_tokens'])
    # Reasoning is an output subset, never an additional token charge.
    return result


def estimate_api_cost(model, raw, *, snapshot=None, service_tier=None):
    snapshot = snapshot or pricing_snapshot()
    unknown = {'estimated_cost': None, 'actual_billed_cost': None, 'currency': 'USD',
               'price_basis': snapshot, 'cost_status': 'USAGE_DETAILS_MISSING'}
    rate = snapshot['models'].get(model)
    if rate is None:
        return {**unknown, 'cost_status': 'MODEL_PRICE_UNKNOWN'}
    if service_tier not in (None, 'auto', 'default'):
        return {**unknown, 'cost_status': 'SERVICE_TIER_PRICE_UNKNOWN'}
    u = normalize_usage(raw)
    required = ('input_tokens', 'cached_input_tokens', 'cache_write_tokens', 'output_tokens')
    if any(u[k] is None for k in required):
        return unknown
    i, cached, written, o = [u[k] for k in required]
    if cached + written > i or (u['reasoning_tokens'] is not None and u['reasoning_tokens'] > o) or u['total_matches_reported'] is False:
        return {**unknown, 'cost_status': 'INCONSISTENT_USAGE'}
    if i > snapshot['long_context_input_threshold']:
        return {**unknown, 'cost_status': 'LONG_CONTEXT_PRICE_REQUIRES_REVIEW'}
    d = lambda x: Decimal(str(x))
    components = {
        'uncached_input': d(i-cached-written)*d(rate['input_per_million']),
        'cached_input': d(cached)*d(rate['cached_input_per_million']),
        'cache_write': d(written)*d(rate['input_per_million'])*d(rate['cache_write_multiplier']),
        'output_including_reasoning': d(o)*d(rate['output_per_million']),
    }
    components = {key: float(value/1_000_000) for key, value in components.items()}
    return {**unknown, 'estimated_cost': float(sum(d(v) for v in components.values())),
            'cost_components_usd': components, 'cost_status': 'ESTIMATED_FROM_PUBLISHED_STANDARD_RATES'}


def usage_record(*, role, purpose, model, attempt_id, envelope=None, status=None, elapsed_seconds=None):
    envelope = envelope if isinstance(envelope, dict) else {}
    raw = envelope.get('usage')
    return {
        'version': 1, 'role': role, 'purpose': purpose, 'provider': 'openai', 'model': model,
        'attempt_id': attempt_id, 'response_id': envelope.get('id'),
        'response_status': envelope.get('status'), 'status': status or envelope.get('status', 'unknown'),
        'service_tier': envelope.get('service_tier'), 'recorded_at': datetime.now(timezone.utc).isoformat(),
        'elapsed_seconds': elapsed_seconds, 'reported_usage': raw, 'tokens': normalize_usage(raw),
        'api_requests': 1, 'cli_invocations': 0,
        **estimate_api_cost(model, raw, service_tier=envelope.get('service_tier')),
    }


def _summarize(records):
    tokens, missing, means = {}, {}, {}
    for key in TOKEN_FIELDS:
        known = [normalize_usage(r.get('reported_usage'))[key] for r in records]
        values = [v for v in known if v is not None]
        tokens[key] = sum(values) if values else None
        missing[key] = len(records)-len(values)
        means[key] = sum(values)/len(values) if values else None
    costs = [r.get('estimated_cost') for r in records if r.get('estimated_cost') is not None]
    return {
        'calls': len(records),
        'completed_responses': sum(r.get('status', r.get('response_status')) == 'completed' for r in records),
        'failed_or_incomplete_or_unknown': sum(r.get('status', r.get('response_status')) != 'completed' for r in records),
        'missing_usage_calls': sum(not isinstance(r.get('reported_usage'), dict) for r in records),
        'token_totals_known': tokens, 'token_averages_known': means,
        'average_context_tokens': means['input_tokens'],
        'missing_token_field_calls': missing,
        'estimated_cost_usd_known': float(sum(Decimal(str(c)) for c in costs)) if costs else None,
        'missing_cost_calls': len(records)-len(costs),
        'actual_billed_cost': None,
        'cost_status': 'Estimate only; reconcile separately with billing records.',
    }


def summarize_run(run_dir, output_dir=None):
    """Read every API usage.json, including failed/retried calls and copied rounds.

    Duplicate response IDs count once. Records without IDs use attempt_id; legacy
    records without either ID remain separate and are reported as unverifiable.
    """
    run_dir = Path(run_dir).resolve()
    if not run_dir.is_dir():
        raise ValueError('RUN_DIRECTORY_NOT_FOUND')
    output_dir = Path(output_dir).resolve() if output_dir else run_dir/'api-usage'
    unique, duplicates, errors, unverified = {}, [], [], []
    for path in sorted(run_dir.rglob('usage.json')):
        try:
            row = json.loads(path.read_text())
            if not isinstance(row, dict):
                raise ValueError('USAGE_NOT_OBJECT')
            if row.get('provider') != 'openai' or row.get('cli_invocations', 0):
                continue
            row = dict(row)
            if not row.get('response_id'):
                envelope_path = path.parent.parent/'02-raw-response/api-execution.json'
                if envelope_path.is_file():
                    envelope = json.loads(json.loads(envelope_path.read_text())['text'])
                    row['response_id'] = envelope.get('id')
                    row.setdefault('response_status', envelope.get('status'))
            row.setdefault('purpose', 'unmapped')
            row['usage_path'] = str(path.relative_to(run_dir))
            key = ('response', row['response_id']) if row.get('response_id') else (
                ('attempt', row['attempt_id']) if row.get('attempt_id') else ('path', row['usage_path']))
            if key[0] == 'path':
                unverified.append(row['usage_path'])
            if key in unique:
                old = unique[key]
                duplicates.append({'key': list(key), 'kept': old['usage_path'], 'duplicate': row['usage_path'],
                    'usage_conflict': old.get('reported_usage') != row.get('reported_usage')})
                if not isinstance(old.get('reported_usage'), dict) and isinstance(row.get('reported_usage'), dict):
                    unique[key] = row
            else:
                unique[key] = row
        except (ValueError, OSError, KeyError, TypeError) as error:
            errors.append({'path': str(path.relative_to(run_dir)), 'error': str(error)})
    rows = list(unique.values())
    purposes, stages, models = defaultdict(list), defaultdict(list), defaultdict(list)
    for row in rows:
        purposes[row['purpose']].append(row)
        stages[row.get('role', 'unknown')].append(row)
        models[row.get('model', 'unknown')].append(row)
    summary = {
        'version': 1, 'run_dir': str(run_dir), 'generated_at': datetime.now(timezone.utc).isoformat(),
        'total': _summarize(rows), 'by_purpose': {k: _summarize(v) for k, v in sorted(purposes.items())},
        'by_role': {k: _summarize(v) for k, v in sorted(stages.items())},
        'by_model': {k: _summarize(v) for k, v in sorted(models.items())},
        'duplicates': duplicates, 'legacy_dedup_unverifiable': unverified, 'read_errors': errors,
        'calls': rows,
        'notes': ['Reasoning is included in output tokens, never added twice.',
                  'Means use known fields only; missing field counts are explicit.',
                  'All recorded attempts count, regardless of response or later validation success.',
                  'Costs are recorded estimates, not provider billing. Unknown costs are not zero.'],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    fmt = lambda v: 'Unconfirmed' if v is None else f'{v:,.6f}' if isinstance(v, float) else f'{v:,}'
    lines = ['# The API usage estimate', '', f'Original run: `{run_dir}`', '',
             'Readings: This is a complete/by_purpose/by_role → call usage_path copy of README → summary.json.', '',
             'The average input is the average of the actual API input tokens. The output includes the inference tokens.',
             'It includes failures, incidents, and calls, and the response_id only compute the same duplicate output once.',
             'The cost is the estimate of the public key at the time of the call, and it\'s not the actual charge. 0is not.', '',
             'Usage call average input average output average inference total token verifier cost USD verifier use zero cost',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for purpose, item in list(summary['by_purpose'].items()) + [('All', summary['total'])]:
        a = item['token_averages_known']
        values = [item['calls'], a['input_tokens'], a['output_tokens'], a['reasoning_tokens'],
                  item['token_totals_known']['total_tokens'], item['estimated_cost_usd_known'],
                  item['missing_usage_calls'], item['missing_cost_calls']]
        lines.append('| '+purpose+' | '+' | '.join(fmt(v) for v in values)+' |')
    lines += ['', f"Duplicates {len(duplicates)}That\x27s a reading error. {len(errors)}That\x27s a past ID. {len(unverified)}That one.",
              'The single source and snapshot hash is saved when you call on summary.json\'s calls.price_basis.',
              'Check the verification output of the following statement for the following schema/response failure: completed is the API response state.']
    (output_dir/'README.md').write_text('\n'.join(lines)+'\n')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    parser.add_argument('--output')
    args = parser.parse_args()
    result = summarize_run(args.run, args.output)
    print(json.dumps(result['total'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
