"""Observable answer checks and reports with fixed planned denominators."""
import re
from pathlib import Path

run_layout = __import__('finarch.experiments.90-operations.run_layout', fromlist=['*'])
from finarch.paths import SOURCE
from collections import Counter, defaultdict

from finarch.shared.reference import Reference, compare
from finarch.dataset.shared.calculation.number_normalization import load_rules, normalize_number

configuration = __import__('finarch.experiments.90-operations.storage', fromlist=['configuration']).configuration
now = __import__('finarch.experiments.90-operations.storage', fromlist=['now']).now
read = __import__('finarch.experiments.90-operations.storage', fromlist=['read']).read
rows = __import__('finarch.experiments.90-operations.storage', fromlist=['rows']).rows
write = __import__('finarch.experiments.90-operations.storage', fromlist=['write']).write
write_text = __import__('finarch.experiments.90-operations.storage', fromlist=['write_text']).write_text
call_layout = __import__('finarch.experiments.01-evaluation.03-execution.call_layout', fromlist=['*'])
LABELS = __import__('finarch.experiments.00-input.dataset', fromlist=['LABELS']).LABELS
compare_answer = __import__('finarch.experiments.01-evaluation.04-validation.answer_format', fromlist=['compare_answer']).compare_answer
metadata = __import__('finarch.experiments.01-evaluation.04-validation.answer_format', fromlist=['metadata']).metadata
answer_contract = __import__('finarch.experiments.01-evaluation.02-request.answer_contract', fromlist=['*'])
request_order = __import__('finarch.experiments.01-evaluation.02-request.request_order', fromlist=['*'])


VARIANT_ORDER = {label: index for index, label in enumerate(('ORIGINAL', *LABELS))}
VARIANT_NAMES = {
    'ORIGINAL': 'ORIGINAL',
    'IC_VALUE_01_BEFORE': 'IC-value-before',
    'IC_VALUE_01_AFTER': 'IC-value-after',
    'IC_SOURCE_A_ONLY': 'IC-source-before',
    'IC_SOURCE_B_ONLY': 'IC-source-after',
    'IC_RELATION_01': 'IC-relation',
    'EA_01': 'EA-01',
    'EA_02': 'EA-02',
}


def group_order(item):
    experiment, variant, prompt, reasoning = item[0]
    return experiment, VARIANT_ORDER.get(variant, len(VARIANT_ORDER)), variant, prompt, reasoning


def screen(response, public, private):
    v5 = 'answer_meta' in response and 'status' not in response
    structured = v5 or (('answer_meta' in response or 'negative' in response) and 'status' in response)
    answer = '' if response['answer'] is None else str(response['answer'])
    quotes = [{'quote': q, 'found': bool(q) and (q in public['question'] or q in public['context'])}
              for q in response['evidence']]
    numeric_text = re.sub(r'([+\-−])\s*[$€£₹]\s*(?=\d)', lambda m: '-' if m[1] == '−' else m[1], answer)
    numbers = re.findall(r'(?<![\w.])[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:[eE][+-]?\d+)?(?![\w.])', numeric_text)
    result = {'evidence_quotes': quotes, 'all_quotes_present': all(q['found'] for q in quotes) if quotes else None,
              'abstention_marker_detected': bool(re.search(
                  r'cannot (?:be |reliably |uniquely )?(?:determine|calculate|answer)|insufficient|not enough|underdetermined|unable to|cannot provide',
                  answer, re.I)),
              'semantic_assessment': 'NOT_REVIEWED', 'numeric_tokens': numbers,
              'numeric_comparison_status': 'NOT_EVALUATED',
              'numeric_extraction_adjustment': 'SIGN_BEFORE_CURRENCY' if numeric_text != answer else None}
    if structured:
        meta = metadata(response)
        if v5:
            result.update(answer_contract.observations(response))
        else:
            result.update(response_format='FinancialAnswerMagnitudeV4' if 'answer_meta' in response else 'FinancialAnswerMagnitudeV3',
                          reported_status=response['status'], declared_abstention=response['status'] == 'abstained')
        result.update(reported_negative=meta['negative'], reported_scale=meta['scale'],
                      scale_assessment='RECORDED_NO_AUTOMATIC_RESCALING',
                      unit_assessment='IMPLICIT_IN_QUESTION_CONTEXT_NOT_SEPARATELY_SCORED')
        if private and private['experiment'] == 1 and (type(response['answer']) in (int, float) if v5 else response['status'] == 'answered'):
            result.update(numeric_comparison=compare_answer(response, private['reference']),
                          numeric_comparison_status='COMPARED_SIGNED_DECIMAL_IN_QUESTION_SCALE')
        return result
    if private and private['experiment'] == 1 and len(numbers) == 1 and not result['abstention_marker_detected']:
        steps = []
        try:
            rules, sha = load_rules()
            normalized, applied = normalize_number(numbers[0], rules, steps)
            # Parentheses denote a negative quantity only when they enclose this sole numeric answer.
            if re.search(r'\(\s*[$€£₹]?\s*' + re.escape(numbers[0]) + r'\s*\)', answer):
                normalized = '-' + normalized.lstrip('+')
            result.update(numeric_comparison=compare(normalized, Reference(**private['reference'])),
                          numeric_comparison_status='COMPARED_NUMBER_ONLY',
                          number_rules_sha256=sha, normalization_steps=steps, applied_rules=applied)
        except (ValueError, ArithmeticError) as error:
            result.update(numeric_comparison_status='NUMBER_FORMAT_REVIEW', number_error=str(error),
                          normalization_steps=steps)
    return result


def build(root, final_status=None):
    config = configuration(root)
    selection = request_order.selection_from_manifests(root)
    state = read(root / 'state.json', {})
    if final_status is not None:
        state = {**state, 'status': final_status}
    requests_by_model = {model['key']: rows(run_layout.requests(root, model['key']))
                         for model in config['models']}
    design_lines = []
    for model in config['models']:
        parts = []
        for experiment, label in ((1, 'Original'), (2, 'Variant')):
            planned = [r for r in requests_by_model[model['key']] if r['experiment'] == experiment]
            conditions = ', '.join(f'{run_layout.prompt_label(prompt)}/Reasoning {reasoning.upper()}' for prompt, reasoning in sorted({
                (r['prompt_condition'], r['reasoning']) for r in planned})) or 'No request for your help.'
            parts.append(f'{label} {len(planned)}What?{conditions})')
        design_lines.append(f"- {model['key']}: " + ' · '.join(parts))
    public = {r['item_id']: r for r in rows(run_layout.inputs(root) / 'public.jsonl')}
    private = {} if run_layout.ordered(root) else {r['item_id']: r for r in rows(run_layout.inputs(root) / 'private.jsonl')}
    summary = {'run_id': root.name, 'updated_at': now(), 'status': state.get('status', 'PREPARED'),
               'cache_policy': config.get('cache_policy'),
               'cache_exceptions': {m['key']: m['_cache_exception'] for m in config['models'] if m.get('_cache_exception')},
               'originals': selection['originals'], 'variants': selection['variants'], 'models': [],
               'semantic_evaluation': 'NOT_REVIEWED', 'billed_cost_usd': None,
               'billing_note': 'Access mode and token-based costs recorded separately; not an invoice.'}
    lines = [f'# {root.name} The experimental report.', '', f"State of play: **{summary['status']}** · Renewal: {summary['updated_at']}", '',
             f"Source text {selection['originals']}That\x27s an automatic check-through transformation. {selection['variants']}entries.",
             'The Q/C numbers delivered to the array are confirmed by the input of the model-by-model request manifest. The correct answer value A and the correct answer symbol are used only for local comparison.', '',
             'It\'s a cleaner of the actual stored request criteria conditions and conditions that weren\'t already executed in the past.', '',
             *design_lines, '',
             'The model is to be used to validate the application form and the validation of the application form.',
             '|---|---:|---:|---:|---:|---:|---:|---:|']
    if summary['cache_exceptions']:
        lines[4:4] = ['**The cached exception to this execution.**Gemini allows silent input caching with user approval. '
                      'It prohibits reuse of explicit caches and other executable responses, and records the missing usage as inaccurate. '
                      'separately from the original frozen cache-disable policy `cache-exceptions.json`I\'m keeping the approval.', '']
    elif config.get('cache_policy'):
        lines[4:4] = ['**Caching is prohibited.**Provider input cache: Prohibit reuse of read-write and other execution responses. '
                      'If the transmission settings that turn off the cache are not verified, they block before calling, and the usage gap is not 0It\'s not dealt with.', '']
    if summary['status'] == 'CACHE_POLICY_BLOCKED':
        lines[4:4] = ['**I didn\'t see the running backup lock lock function.** The plan drain below is not the response numbers collected. '
                      'Whether the actual call is the number of attempts per model and the `cache-preflight.json`I\'ll check it out.', '']
    detail_lines = []
    for model in config['models']:
        folder = run_layout.execution(root, model['key'])
        requests = requests_by_model[model['key']]
        call_layout.check_manifest(folder, requests)
        results, counts, groups = [], Counter(), defaultdict(Counter)
        input_tokens = output_tokens = 0
        reasoning_tokens = reasoning_usage_records = 0
        equivalent, unknown_usage, attempts_count, cache_read, cache_creation = 0.0, 0, 0, 0, 0
        cache_checks = Counter()
        cache_write_usage_records = 0
        paid_estimate = 0.0
        paid_api_estimate = 0.0
        paid_api_cost_records = 0
        provider_reported_cost = 0.0
        provider_reported_cost_records = 0
        output_limits = Counter()
        for request in requests:
            trial = request['trial_id']
            attempts = [p / 'result.json' for p in call_layout.attempt_dirs(folder, request)]
            for attempt in attempts:
                attempts_count += 1
                result = read(attempt, {'status': 'UNKNOWN_DELIVERY', 'usage': None})
                cache_checks[result.get('cache_check', {}).get('status', 'NOT_AUDITED')] += 1
                usage = result.get('usage')
                if not usage:
                    if result.get('status') != 'BATCH_PENDING':
                        unknown_usage += 1
                    continue
                if model['transport'] == 'codex_cli':
                    incoming = usage.get('input_tokens', 0)
                    outgoing = usage.get('output_tokens', 0)
                    cache_read += usage.get('cached_input_tokens', 0)
                    if type(usage.get('cache_write_input_tokens')) is int and usage['cache_write_input_tokens'] >= 0:
                        cache_creation += usage['cache_write_input_tokens']
                        cache_write_usage_records += 1
                    if usage.get('reasoning_output_tokens') is not None:
                        reasoning_tokens += usage['reasoning_output_tokens']
                        reasoning_usage_records += 1
                elif model['transport'] == 'orca_api':
                    incoming, outgoing = usage.get('prompt_tokens', 0), usage.get('completion_tokens', 0)
                    details = usage.get('prompt_tokens_details') or {}
                    cached, written = details.get('cached_tokens'), details.get('cache_write_tokens')
                    if type(cached) is int and cached >= 0:
                        cache_read += cached
                    if type(written) is int and written >= 0:
                        cache_creation += written
                        cache_write_usage_records += 1
                    reasoning = (usage.get('completion_tokens_details') or {}).get('reasoning_tokens')
                    if type(reasoning) is int and reasoning >= 0:
                        reasoning_tokens += reasoning
                        reasoning_usage_records += 1
                    cost = result.get('token_cost_estimate_usd')
                    if cost is not None:
                        equivalent += cost
                        paid_api_estimate += cost
                        paid_api_cost_records += 1
                    reported_cost = result.get('provider_reported_cost_usd')
                    if reported_cost is not None:
                        provider_reported_cost += reported_cost
                        provider_reported_cost_records += 1
                elif model['transport'] in ('openai_responses', 'openai_batch'):
                    incoming, outgoing = usage.get('input_tokens', 0), usage.get('output_tokens', 0)
                    details = usage.get('input_tokens_details') or {}
                    cached = details.get('cached_tokens')
                    if type(cached) is int and cached >= 0:
                        cache_read += cached
                    written = details.get('cache_write_tokens')
                    if type(written) is int and written >= 0:
                        cache_creation += written
                        cache_write_usage_records += 1
                    reasoning = (usage.get('output_tokens_details') or {}).get('reasoning_tokens')
                    if type(reasoning) is int and reasoning >= 0:
                        reasoning_tokens += reasoning
                        reasoning_usage_records += 1
                    cost = result.get('token_cost_estimate_usd')
                    if cost is not None:
                        equivalent += cost
                        if model['transport'] == 'openai_batch':
                            paid_estimate += cost
                        else:
                            paid_api_estimate += cost
                        paid_api_cost_records += 1
                elif model['transport'].startswith('gemini'):
                    incoming = usage.get('promptTokenCount', 0)
                    outgoing = usage.get('candidatesTokenCount', 0) + usage.get('thoughtsTokenCount', 0)
                    cached = usage.get('cachedContentTokenCount', 0)
                    cache_read += cached
                    prices = result.get('price_per_million', {'input': 0.1, 'output': 0.4})
                    # Do not invent an implicit-cache discount when its rate is not configured.
                    cost = ((incoming - cached) * prices['input'] + cached * prices.get('cached_input', prices['input']) + outgoing * prices['output']) / 1e6
                    equivalent += cost
                    if result.get('billing_mode') == 'PAID_BATCH':
                        paid_estimate += cost
                    if type(usage.get('thoughtsTokenCount')) is int:
                        reasoning_tokens += usage['thoughtsTokenCount']
                        reasoning_usage_records += 1
                else:
                    incoming = (usage.get('input_tokens', 0) + usage.get('cache_read_input_tokens', 0)
                                + usage.get('cache_creation_input_tokens', 0))
                    outgoing = usage.get('output_tokens', 0)
                    if model['transport'] == 'vllm_local' and type(usage.get('reasoning_output_tokens')) is int:
                        reasoning_tokens += usage['reasoning_output_tokens']
                        reasoning_usage_records += 1
                    cache_read += usage.get('cache_read_input_tokens', 0)
                    cache_creation += usage.get('cache_creation_input_tokens', 0)
                    cache_write_usage_records += int('cache_creation_input_tokens' in usage)
                    cost = result.get('reported_equivalent_usd')
                    equivalent += cost or 0
                    if model['transport'] in ('anthropic_api', 'anthropic_batch') and cost is not None:
                        if model['transport'] == 'anthropic_batch':
                            paid_estimate += cost
                        else:
                            paid_api_estimate += cost
                        paid_api_cost_records += 1
                input_tokens += incoming
                output_tokens += outgoing
            pending_status = 'BATCH_PENDING' if state.get('models', {}).get(model['key'], {}).get('status') == 'BATCH_PENDING' else 'NOT_RUN'
            latest = read(attempts[-1], {'status': 'UNKNOWN_DELIVERY', 'usage': None}) if attempts else {'status': pending_status}
            row = {k: request[k] for k in ('trial_id', 'item_id', 'experiment', 'variant', 'case', 'prompt_condition', 'reasoning')}
            row.update(status=latest['status'], attempts=len(attempts),
                       result_path=str(attempts[-1].relative_to(root)) if attempts and attempts[-1].exists() else None)
            row['transport'] = latest.get('transport', model['transport'])
            if model.get('output_budget'):
                row['max_output_tokens'] = latest.get('max_output_tokens', request['max_output_tokens']) if attempts else None
                row['output_budget'] = latest.get('output_budget')
                if row['max_output_tokens'] is not None:
                    output_limits[row['max_output_tokens']] += 1
            row['billing_mode'] = latest.get('billing_mode',
                'USER_DESIGNATED_FREE_KEY' if attempts and row['transport'] == 'gemini_free_api' else
                'SUBSCRIPTION' if attempts and row['transport'] == 'claude_code' else 'NOT_RUN')
            if latest['status'] == 'VALID':
                row['response'] = latest['response']
                row['checks'] = screen(latest['response'], public[row['item_id']], private.get(row['item_id']))
                if request['response_schema'].get('title') in answer_contract.STRUCTURAL_TITLES:
                    row['checks']['response_format'] = request['response_schema']['title']
            elif 'error' in latest:
                row['error'] = latest['error']
            if latest.get('schema_errors'):
                row['schema_errors'] = latest['schema_errors']
            if latest.get('finish_reason'):
                row['finish_reason'] = latest['finish_reason']
            row['call_path'] = call_layout.publish(root, folder, request, row)
            results.append(row)
            counts[row['status']] += 1
            group = groups[(row['experiment'], row['variant'], row['prompt_condition'], row['reasoning'])]
            group['planned'] += 1
            group[row['status']] += 1
            if 'checks' in row:
                if type(row['checks'].get('abstention_marker_detected')) is bool:
                    group['abstention_marker_detected'] += int(row['checks']['abstention_marker_detected'])
                if type(row['checks'].get('declared_abstention')) is bool:
                    group['declared_abstentions'] += int(row['checks']['declared_abstention'])
                if 'numeric_answer_present' in row['checks']:
                    group['numeric_answers_absent'] += int(not row['checks']['numeric_answer_present'])
                comparison = row['checks'].get('numeric_comparison')
                if comparison:
                    group['numeric_compared'] += 1
                    group['numeric_matches'] += int(comparison['matches'])
        model_summary = {'model': model['key'], 'transport': model['transport'], 'planned': len(requests),
            'statuses': dict(counts), 'attempts': attempts_count, 'input_tokens': input_tokens,
            'output_tokens_including_thinking': output_tokens, 'cache_read_tokens': cache_read,
            'reported_reasoning_output_tokens': reasoning_tokens if reasoning_usage_records else None,
            'attempts_with_reasoning_usage': reasoning_usage_records,
            'cache_creation_tokens': cache_creation if cache_write_usage_records else None,
            'attempts_with_cache_write_usage': cache_write_usage_records, 'attempts_without_usage': unknown_usage,
            'cache_verification': {'status': 'NOT_CALLED' if not attempts_count else
                                   'VERIFIED_ZERO' if cache_checks['VERIFIED_ZERO'] == attempts_count else 'NOT_VERIFIED_ZERO',
                                   'attempts_by_status': dict(cache_checks)},
            'api_equivalent_usd': None if model['transport'] == 'codex_cli' else round(equivalent, 8), 'billed_cost_usd': None,
            'incremental_api_charge_usd': 0 if model['transport'] == 'codex_cli' else None,
            'paid_batch_usage_cost_estimate_usd': round(paid_estimate, 8),
            'paid_api_usage_cost_estimate_usd': round(paid_api_estimate, 8),
            'attempts_with_paid_api_cost_estimate': paid_api_cost_records,
            'response_transport_counts': dict(Counter(r['transport'] for r in results if r['status'] != 'NOT_RUN')),
            'provider_state': state.get('models', {}).get(model['key'], {}),
            'groups': [{'experiment': k[0], 'variant': k[1], 'prompt': k[2], 'reasoning': k[3], **v}
                       for k, v in sorted(groups.items(), key=group_order)]}
        if model['transport'] == 'orca_api':
            model_summary.update(provider_reported_cost_usd=round(provider_reported_cost, 8) if provider_reported_cost_records else None,
                attempts_with_provider_reported_cost=provider_reported_cost_records,
                cost_status='INLINE_PROVIDER_REPORTED_NOT_SETTLEMENT_VERIFIED',
                implicit_cache_exception=model.get('_cache_exception'),
                cost_estimate_note='Published UTC peak rate at request start; automatic cache reads billed at cached-input rate; cache-write usage unknown when absent.')
            if model.get('output_budget'):
                model_summary.update(output_budget=model['output_budget'],
                                     latest_attempt_output_limits=dict(output_limits))
            if model.get('returned_model_policy'):
                model_summary['returned_model_policy'] = model['returned_model_policy']
        if model['transport'] == 'vllm_local':
            model_summary.update(cache_read_tokens=None, cache_creation_tokens=None,
                                 incremental_api_charge_usd=0, api_equivalent_usd=None)
        if model.get('_cache_exception'):
            model_summary['cache_exception'] = model['_cache_exception']
            model_summary['cache_verification']['effective_policy'] = 'IMPLICIT_CACHE_ALLOWED_BY_USER'
            model_summary['cache_verification']['missing_usage'] = 'UNKNOWN_NOT_ZERO'
        if model['transport'].startswith('gemini'):
            model_summary['cost_estimate_note'] = 'Configured input rate is used for implicit-cache tokens unless a cached_input rate is configured; not an invoice.'
        summary['models'].append(model_summary)
        write_rows = __import__('finarch.experiments.90-operations.storage', fromlist=['write_rows']).write_rows
        write_rows(run_layout.validation(root, model['key']) / 'results.jsonl', results)
        write(run_layout.validation(root, model['key']) / 'summary.json', model_summary)
        awaiting = counts['NOT_RUN'] + counts['BATCH_PENDING']
        failed = len(requests) - counts['VALID'] - awaiting
        cost_display = 'Subscription usage: API transfer by default' if model['transport'] == 'codex_cli' else f'{equivalent:.6f}'
        lines.append(f"|{model['key']}|{len(requests)}|{counts['VALID']}|{failed}|{awaiting}|{input_tokens}|{output_tokens}|{cost_display}|")
        provider_state = model_summary['provider_state']
        detail_lines += ['', f"## {model['key']} The results are conditional.", '',
                         f"Running state: `{provider_state.get('status', 'PENDING')}Try it. {attempts_count}That\x27s the sub-reverse of the use. {unknown_usage}That one."]
        if model['transport'] == 'orca_api':
            reported_note = f"${provider_reported_cost:.6f}（{provider_reported_cost_records}entries)" if provider_reported_cost_records else 'Sub-revenue'
            if model.get('returned_model_policy'):
                identifiers = ', '.join(model['returned_model_policy']['accepted_additional_identifiers'])
                detail_lines += ['', f"Additional return model names approved in this run: `{identifiers}`The actual return model name is stored in the model_version of each result. `{model['model']}` and supply path fixed-weight identification is not confirmed. The original result of the stored model name error and raw are preserved, and the response format is re-examined without new calls."]
            budget = model.get('output_budget')
            output_note = (f"The new request includes comments: {budget['base_output_tokens']:,}Token. finish_reason=length requests only the previous one. 2And they will be re-created and run. {budget['max_output_tokens']:,}It stops at the token. {model['output_limits']}And every attempt is kept the same. The policy reads runtime-overrides.json, the actual limit is the request.json;provider-request-wire.json of the attempt."
                           if budget else f"Includes: {model['output_limits']}.")
            detail_lines += ['', f"Orca DeepSeek V4.1 Flash: R⁻ OFF / R⁺ max, {output_note} Now, if you\x27re going to process it simultaneously, {provider_state.get('concurrency', config['schedule']['concurrency'])}And the first one is the end of the line. {config['schedule']['concurrency']}entries.",
                             f"Returns usage·per-view publicity by estimate: **${paid_api_estimate:.6f}**Inline cost of providers: {reported_note}It\x27s a pre-tax acquisition and it doesn\x27t add up the two costs.",
                             f"Automatically read the cache {cache_read:,}Tokens, inference output {reasoning_tokens:,}The cache field missing is unknown. `cache-exceptions.json`I\x27m going to write it down."]
        elif model['transport'] == 'openai_responses':
            detail_lines += ['', f"OpenAI is a paid, general API. **${paid_api_estimate:.6f}**And the actual invoice amount is uncertain.",
                             f"Read the returned cache {cache_read:,}Tokens, cashing in {cache_creation:,} tokens ({cache_write_usage_records}The use of items writing records), reasoning output {reasoning_tokens:,}This is a token.{model_summary['cache_verification']['status']}`.",
                             f"The inference conditions are: {model['reasoning_efforts']}After verifying the cache usage of both conditions, the API request is up to {config['schedule']['concurrency']}And we\x27re going to parallelize each items. {config['schedule']['fallback_group_size']}CLI methods that increase the number of calls per CPU don\x27t apply."]
        elif model['transport'] == 'openai_batch':
            detail_lines += ['', f"It\x27s an OpenAI Batch API. **${paid_estimate:.6f}**And the bill is a pre-estimated amount versus the bill.",
                             f"Read the cache. {cache_read:,}The token writing {cache_creation:,}Token, reasoning {reasoning_tokens:,}The result is connected to the query using custom_id."]
        elif model['transport'] == 'anthropic_api':
            detail_lines += ['', f"Claude is a paid messaging API. **${paid_api_estimate:.6f}**And the actual bill is uncertain.",
                             f"Read the returned cache {cache_read:,}Tokens, cashing in {cache_creation:,}This is a token.{model_summary['cache_verification']['status']}`."]
        elif model['transport'] == 'anthropic_batch':
            detail_lines += ['', f"Claude Message Batches API. The cost is calculated by the batch unit and the return usage. **${paid_estimate:.6f}**And the actual bill is uncertain.",
                             f"Read the cache. {cache_read:,}The token writing {cache_creation:,}This is a token.{model_summary['cache_verification']['status']}`. connect to the request with custom_id."]
            if model.get('model') == 'claude-haiku-5-5':
                detail_lines += [f"Haiku 5.5 effort: {model['reasoning_efforts']}.ON is adaptive, OFF is disabled. xhigh/max can\x27t run OFF. {model['output_limits']}."]
        elif model['transport'] == 'vllm_local':
            detail_lines += ['', 'A100The cost of an external API call is 0It\'s a dollar, and the GPU costs a million dollars. '
                             'The engine prefix cache setting; hit record and the cache token reporting of individual responses are separately verified.']
        elif model['transport'] == 'gemini_batch':
            thinking = (f"thinkingLevel={model['thinking_levels']} · No reasoning OFF conditions"
                        if model.get('thinking_levels') else f"thinkingBudget: OFF=0 / ON={model.get('thinking_budget')}")
            detail_lines += ['', f"It\x27s the Native Gemini Batch. {thinking}- Output is low. {model.get('output_limits')}.",
                             f"Estimated cost based on usage: **${paid_estimate:.6f}**The cache discounted unit is the total input unit when the default is, and the amount of the charge is uncertain.",
                             f"cache: I know.{model_summary['cache_verification']['status']}`. The cache usage decline is uncertain."]
        elif model['transport'] != 'codex_cli':
            detail_lines += ['', f"Payment Batch usage-based cost estimates: **${paid_estimate:.6f}**The amount of the free-of-charge call is shown together in the table above, and the actual charge is unknown."]
        if model['transport'] == 'codex_cli':
            schedule = config['schedule']
            token_note = (f"Reported cached input: {cache_read:,} tokens, already included in total input. Reported reasoning output: {reasoning_tokens:,} tokens ({reasoning_usage_records} usage records), already included in total output; do not add it again."
                          if attempts_count else 'No model was called, so input, cached-input, reasoning, and output usage have not been observed. Zeros in the table are totals for an unexecuted run.')
            detail_lines += ['', 'It\'s a codex chatgpt subscription call. 0And the usage of the subscription fee and the calculation is separate. The input, the cache, and the output tokens are calculated from the CLI source log.',
                             token_note,
                             f"The mapping of the inference conditions: {model['reasoning_efforts']}CLI does not consider the output limit to be the same as the API thinking_budget.",
                             (f"When the call starts, `resources.jsonl`in {schedule['monitor_interval_seconds']}It records the CPU memory and the synchronous processing limit every second. {schedule['initial_concurrency']}, CPU {schedule['cpu_threshold_percent']}If less than a percent, {schedule['increase_by']}And it\x27s increasing with each items. {schedule['concurrency']}It\x27s a items. {schedule['memory_threshold_percent']}% or more {schedule['minimum_available_memory_gb']}If it\x27s less than GB, it keeps the new process input."
                              if all(k in schedule for k in ('monitor_interval_seconds','initial_concurrency','cpu_threshold_percent','increase_by','concurrency','memory_threshold_percent','minimum_available_memory_gb'))
                              else 'Simultaneous run and resource settings check the schedule of config.json and the actual resources.jsonl.')]

        if provider_state.get('reason'):
            detail_lines += ['', str(provider_state['reason'])]
        if provider_state.get('status') == 'CACHE_POLICY_BLOCKED':
            detail_lines += ['', '**The new model call was blocked by the cache preview.** '
                             '0The token sum shown here is a mismatch, and it doesn\'t mean that the cache is tied to the experiment. '
                             'The reason and the reason `cache-preflight.json`is the location.']
        if provider_state.get('requests_per_day'):
            detail_lines += ['', f"The actual provider limit: per minute {provider_state.get('requests_per_minute', 'Unconfirmed')}One day. {provider_state['requests_per_day']}That one."]
        if run_layout.ordered(root):
            detail_lines += ['', 'The number of times the number of times a number is equal to the number of years the number of days the number of terms is equal to',
                             '|---|---|---|---|---:|---:|---:|']
        else:
            detail_lines += ['', 'The test is a random variable, the prediction is a random number, the predictive number is a random random number, and the predictive numbers are a random number.',
                             '|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|']
        for group in model_summary['groups']:
            prefix = f"|{group['experiment']}|{VARIANT_NAMES.get(group['variant'], group['variant'])}|{group['prompt']}|{group['reasoning']}|{group['planned']}|{group.get('VALID', 0)}|"
            detail_lines.append(prefix + (f"{group.get('numeric_answers_absent', 0)}|" if run_layout.ordered(root) else
                f"{group.get('numeric_compared', 0)}|{group.get('numeric_matches', 0)}|{group.get('abstention_marker_detected', '—')}|{group.get('declared_abstentions', '—')}|{group.get('numeric_answers_absent', '—')}|"))
        write_text((run_layout.validation(root, model['key']) if run_layout.ordered(root) else folder) / 'README.md', run_layout.template(root, 'model-readme-template.md').read_text().format(
            model=model['key'], transport=model['transport'], planned=len(requests), valid=counts['VALID']))
    lines += detail_lines + ['', '## The results and the cost', '',
              'The table is IC-value-before → IC-valure-after → IC-source-before ← IC-sources-after →01 → EA-02 IC-source before/after is the location of the connected value parent. A/B separates the claim that assigned the source, and the source type ID is stored in summary.json. It doesn\'t judge the two properties as having the same effect.', '',
              'The call path and usage are recorded in this execution\'s config.json·city-by-city result.json. The paid API·batch cost is an estimate calculated as the difference between the return token and the corresponding path, and the actual charge is uncertain. 0It\'s not considered a token.',
              'V3/V4 combines the size of the answer with the negative, and V5/V6 compares the symbol of the answer itself to the exact number of the answer. The scale records and does not multiply again. V2 maintains the comparison rules at the time. It is not the exact number that is determined to the meaning of unit-ratio. The stated observation state is the dry of V3/V4. The absence of a numerical answer in V5/V6, and the validity of the observation, distinguishes the content of the resulting statement from the state of the observed state. 02And I\'m going to check it separately from the data in _analysis.',
              'The Ubo-expression detection is the string observation of the response. 2The fact that you passed an automated production test is not proof that the paragraph can\'t answer. 02And I\'ll check it separately in _analysis.', '',
              '## Reopen and file', '',
              f'`PYTHONPATH=src .venv/bin/python -m finarch.experiments.01-evaluation.pipeline run --run {root}`', '',
              'When you reach the free day-to-day limit, the provider stops running. `--resume-limits`Re-opened. Requests that are not known whether to be delivered do not call automatic override.', '',
              'By model. `01-requests/manifest.jsonl`It\'s the running standard that preserves the case connection, the experimental conditions, the full input, the prompt scheme. `03-results/results.jsonl`It\'s the actual response and testing, `Calls/<Help>/<type>/<Helping>-P0-R-off.json`The reading request-response set, type sub `I\'m going to try to get a copy of this.`The selection order of new execution, the verification of the external private sources, is the `events.jsonl` `INPUT_SELECTION`I\'m going to write it down.',
              'Intermodal comparisons are interpreted by identifying the input, output, and output paths of the same execution.']
    if run_layout.ordered(root):
        lines = [line.replace('\ubaa8\ub378\ubcc4 `01-requests/manifest.jsonl`', 'E02The model `manifest.jsonl`')
                 .replace('`03-results/results.jsonl`', '`01_evaluation/04_validation/<model>/results.jsonl`')
                 for line in lines]
        lines += ['', 'This table summarizes the form and functional state.4The numeric-comparisons.jsonl is written, and the [A0]1](../../02_analysis/01_results/README.md)It matches the response to the storage and its evaluation, and it doesn\'t interpret the format pass as a correct rate.']
    write(run_layout.validation(root) / 'summary.json', summary)
    write_text(run_layout.validation(root) / 'REPORT.md', '\n'.join(lines) + '\n')
    # Update navigation without editing a run's frozen documentation template.
    run_template = run_layout.template(root, 'run-readme-template.md').read_text().replace(
        'finarch.experiments.02-model-execution.pipeline', 'finarch.experiments.01-evaluation.pipeline')
    navigation = 'EVALUATION.md' if 'README.md' in read(root / 'manifest.json', {}) else 'README.md'
    write_text(root / navigation, run_template.format(
        run_id=root.name, run_path=str(root), status=summary['status'], originals=selection['originals'], variants=selection['variants']))
    if run_layout.ordered(root):
        documentation = __import__('finarch.experiments.90-operations.run_documentation', fromlist=['render'])
        documentation.render(root)
    return summary
