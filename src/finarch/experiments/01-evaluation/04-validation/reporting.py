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
        for experiment, label in ((1, '원본'), (2, '변형')):
            planned = [r for r in requests_by_model[model['key']] if r['experiment'] == experiment]
            conditions = ', '.join(f'{run_layout.prompt_label(prompt)}/Reasoning {reasoning.upper()}' for prompt, reasoning in sorted({
                (r['prompt_condition'], r['reasoning']) for r in planned})) or '요청 없음'
            parts.append(f'{label} {len(planned)}건 ({conditions})')
        design_lines.append(f"- {model['key']}: " + ' · '.join(parts))
    public = {r['item_id']: r for r in rows(run_layout.inputs(root) / 'public.jsonl')}
    private = {} if run_layout.ordered(root) else {r['item_id']: r for r in rows(run_layout.inputs(root) / 'private.jsonl')}
    summary = {'run_id': root.name, 'updated_at': now(), 'status': state.get('status', 'PREPARED'),
               'cache_policy': config.get('cache_policy'),
               'cache_exceptions': {m['key']: m['_cache_exception'] for m in config['models'] if m.get('_cache_exception')},
               'originals': selection['originals'], 'variants': selection['variants'], 'models': [],
               'semantic_evaluation': 'NOT_REVIEWED', 'billed_cost_usd': None,
               'billing_note': 'Access mode and token-based costs recorded separately; not an invoice.'}
    lines = [f'# {root.name} 실험 보고서', '', f"상태: **{summary['status']}** · 갱신: {summary['updated_at']}", '',
             f"원문 {selection['originals']}건, 자동 검사 통과 변형 {selection['variants']}건입니다.",
             '풀이에 전달한 Q/C·자릿수는 모델별 요청 manifest의 input에서 확인합니다. 정답값 A와 정답 부호는 로컬 비교에만 사용합니다.', '',
             '실제 저장된 요청 기준 조건과 건수입니다. 과거 실행에 없었던 조건은 추가하지 않습니다.', '',
             *design_lines, '',
             '|모델|계획 요청|형식 검사 통과|실패·제한|미실행·배치 대기|기록된 입력 토큰|기록된 출력 토큰|API 환산액(USD)|',
             '|---|---:|---:|---:|---:|---:|---:|---:|']
    if summary['cache_exceptions']:
        lines[4:4] = ['**이번 실행의 캐시 예외**: 사용자 승인으로 Gemini 암묵적 입력 캐시를 허용합니다. '
                      '명시적 캐시와 다른 실행의 응답 재사용은 금지하며, 누락된 사용량은 미확인으로 기록합니다. '
                      '동결된 원래 금지 정책과 별도로 `cache-exceptions.json`에 승인을 보존합니다.', '']
    elif config.get('cache_policy'):
        lines[4:4] = ['**캐시 사용 금지**: 제공자 입력 캐시 읽기·쓰기와 다른 실행의 응답 재사용을 금지합니다. '
                      '캐시를 끄는 전송 설정이 확인되지 않으면 호출 전에 차단하며, 사용량 누락을 0으로 처리하지 않습니다.', '']
    if summary['status'] == 'CACHE_POLICY_BLOCKED':
        lines[4:4] = ['**실행 보류 — 캐시 차단 기능을 확인하지 못했습니다.** 아래 계획 건수는 수집된 응답 수가 아닙니다. '
                      '실제 호출 여부는 모델별 시도 수와 `cache-preflight.json`으로 확인합니다.', '']
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
        cost_display = '구독 사용량·API 환산 미산정' if model['transport'] == 'codex_cli' else f'{equivalent:.6f}'
        lines.append(f"|{model['key']}|{len(requests)}|{counts['VALID']}|{failed}|{awaiting}|{input_tokens}|{output_tokens}|{cost_display}|")
        provider_state = model_summary['provider_state']
        detail_lines += ['', f"## {model['key']} 조건별 결과", '',
                         f"실행 상태: `{provider_state.get('status', 'PENDING')}`. 시도 {attempts_count}건, 사용량 미반환 시도 {unknown_usage}건."]
        if model['transport'] == 'orca_api':
            reported_note = f"${provider_reported_cost:.6f}（{provider_reported_cost_records}건）" if provider_reported_cost_records else '미반환'
            if model.get('returned_model_policy'):
                identifiers = ', '.join(model['returned_model_policy']['accepted_additional_identifiers'])
                detail_lines += ['', f"이 run에서 승인한 추가 반환 모델명: `{identifiers}`. 실제 반환 모델명은 각 result의 model_version에 보존합니다. 요청 별칭은 `{model['model']}`이며 공급 경로 고정·가중치 동일성은 확인하지 않았습니다. 저장된 모델명 오류의 원래 result와 raw는 보존하고, 새 호출 없이 응답 형식을 재검사합니다."]
            budget = model.get('output_budget')
            output_note = (f"새 요청의 출력 상한(추론 포함): {budget['base_output_tokens']:,}토큰. finish_reason=length인 요청만 이전 상한의 2배로 재시도하며 실행 상한 {budget['max_output_tokens']:,}토큰에서 멈춥니다. 최초 동결값 {model['output_limits']}와 각 시도는 그대로 보존합니다. 정책은 runtime-overrides.json, 실제 상한은 attempt의 request.json·provider-request-wire.json을 읽습니다."
                           if budget else f"출력 상한(추론 포함): {model['output_limits']}.")
            detail_lines += ['', f"Orca DeepSeek V4.1 Flash: R⁻ OFF / R⁺ max, {output_note} 현재 동시 처리 한도 {provider_state.get('concurrency', config['schedule']['concurrency'])}건이며 최초 동결 한도는 {config['schedule']['concurrency']}건입니다.",
                             f"반환 usage·시각별 공개 단가 추정: **${paid_api_estimate:.6f}**. 제공자 inline 비용: {reported_note}. 정산 영수증 대조 전이며 두 비용을 합산하지 않습니다.",
                             f"자동 캐시 읽기 {cache_read:,}토큰, 추론 출력 {reasoning_tokens:,}토큰(전체 출력에 포함). 캐시 쓰기 필드 누락은 미확인입니다. 이번 run의 자동 캐시 허용은 `cache-exceptions.json`에 기록합니다."]
        elif model['transport'] == 'openai_responses':
            detail_lines += ['', f"OpenAI 유료 일반 API입니다. 사용량 기반 비용 추정은 **${paid_api_estimate:.6f}**이며 실제 청구액은 미확인입니다. 제공자 Batch 할인은 적용하지 않았습니다.",
                             f"반환된 캐시 읽기 {cache_read:,}토큰, 캐시 쓰기 {cache_creation:,}토큰({cache_write_usage_records}개 쓰기 사용량 기록), reasoning 출력 {reasoning_tokens:,}토큰입니다. 캐시 검사 상태: `{model_summary['cache_verification']['status']}`.",
                             f"추론 조건은 {model['reasoning_efforts']}입니다. 두 조건의 캐시 사용량 확인 후 API 요청을 최대 {config['schedule']['concurrency']}개씩 병렬 처리합니다. 요청 제한 시 {config['schedule']['fallback_group_size']}개로 축소합니다. CPU에 따라 호출 수를 늘리는 CLI 방식은 적용하지 않습니다."]
        elif model['transport'] == 'openai_batch':
            detail_lines += ['', f"OpenAI Batch API입니다. Batch 단가와 반환 사용량으로 계산한 비용은 **${paid_estimate:.6f}**이며 청구서 대조 전 추정액입니다. 일반 API로 대체 호출하지 않습니다.",
                             f"캐시 읽기 {cache_read:,}토큰·쓰기 {cache_creation:,}토큰, reasoning {reasoning_tokens:,}토큰(전체 출력에 포함). 결과는 custom_id로 원요청에 연결합니다."]
        elif model['transport'] == 'anthropic_api':
            detail_lines += ['', f"Claude 유료 Messages API입니다. 반환 사용량과 공개 단가로 추정한 비용은 **${paid_api_estimate:.6f}**이며 실제 청구액은 미확인입니다.",
                             f"반환된 캐시 읽기 {cache_read:,}토큰, 캐시 쓰기 {cache_creation:,}토큰입니다. 캐시 검사 상태: `{model_summary['cache_verification']['status']}`."]
        elif model['transport'] == 'anthropic_batch':
            detail_lines += ['', f"Claude Message Batches API입니다. Batch 단가와 반환 사용량으로 추정한 비용은 **${paid_estimate:.6f}**이며 실제 청구액은 미확인입니다.",
                             f"캐시 읽기 {cache_read:,}토큰·쓰기 {cache_creation:,}토큰입니다. 건별 캐시 검사 상태: `{model_summary['cache_verification']['status']}`. custom_id로 원요청에 연결합니다."]
            if model.get('model') == 'claude-haiku-5-5':
                detail_lines += [f"Haiku 5.5 effort: {model['reasoning_efforts']}. ON은 adaptive, OFF는 disabled입니다. xhigh/max에서는 OFF를 실행할 수 없습니다. 출력 상한(추론 포함): {model['output_limits']}."]
        elif model['transport'] == 'vllm_local':
            detail_lines += ['', 'A100에서 실행한 로컬 vLLM 응답입니다. 외부 API 호출 비용은 0달러이며 GPU 비용은 미산정입니다. '
                             '엔진 prefix cache 설정·hit 기록과 개별 응답의 캐시 토큰 보고 여부는 별도로 확인합니다.']
        elif model['transport'] == 'gemini_batch':
            thinking = (f"thinkingLevel={model['thinking_levels']} · 추론 OFF 조건 없음"
                        if model.get('thinking_levels') else f"thinkingBudget: OFF=0 / ON={model.get('thinking_budget')}")
            detail_lines += ['', f"Native Gemini Batch입니다. {thinking}. 출력 상한: {model.get('output_limits')}.",
                             f"사용량 기반 비용 추정: **${paid_estimate:.6f}**. 캐시 할인 단가 미설정 시 전체 입력 단가로 추정하며 청구액은 미확인입니다.",
                             f"캐시 검사: `{model_summary['cache_verification']['status']}`. 캐시 쓰기 사용량 누락은 미확인입니다."]
        elif model['transport'] != 'codex_cli':
            detail_lines += ['', f"유료 Batch 사용량 기반 비용 추정: **${paid_estimate:.6f}**. 무료·구독 호출의 환산액은 위 표에 함께 표시하고, 실제 청구액은 미확인입니다."]
        if model['transport'] == 'codex_cli':
            schedule = config['schedule']
            token_note = (f"보고된 캐시 입력 {cache_read:,}토큰은 전체 입력에 포함된 값입니다. 반환된 reasoning 출력은 {reasoning_tokens:,}토큰({reasoning_usage_records}개 사용량 기록)이며 전체 출력에 포함된 값이므로 다시 더하지 않습니다."
                          if attempts_count else '모델을 호출하지 않아 입력·캐시·reasoning·출력 사용량의 관측치는 없습니다. 표의 0은 미호출 합계입니다.')
            detail_lines += ['', 'Codex ChatGPT 구독 호출입니다. API 키를 사용하지 않아 추가 API 과금은 0이며, 구독료·계정 사용 한도는 별개입니다. 입력·캐시·출력 토큰은 CLI 원기록에서 집계합니다.',
                             token_note,
                             f"추론 조건 매핑: {model['reasoning_efforts']}. CLI 출력 상한과 API thinking_budget을 동일하게 제어했다고 간주하지 않습니다.",
                             (f"호출이 시작되면 `resources.jsonl`에 {schedule['monitor_interval_seconds']}초마다 CPU·메모리·동시 처리 한도를 기록합니다. 초기 {schedule['initial_concurrency']}개, CPU {schedule['cpu_threshold_percent']}% 미만이면 {schedule['increase_by']}개씩 증가하며 최대 {schedule['concurrency']}개입니다. 메모리 {schedule['memory_threshold_percent']}% 이상 또는 여유 {schedule['minimum_available_memory_gb']}GB 미만이면 새 프로세스 투입을 보류합니다."
                              if all(k in schedule for k in ('monitor_interval_seconds','initial_concurrency','cpu_threshold_percent','increase_by','concurrency','memory_threshold_percent','minimum_available_memory_gb'))
                              else '동시 실행·자원 설정은 config.json의 schedule과 실제 resources.jsonl을 확인합니다.')]

        if provider_state.get('reason'):
            detail_lines += ['', str(provider_state['reason'])]
        if provider_state.get('status') == 'CACHE_POLICY_BLOCKED':
            detail_lines += ['', '**새 모델 호출은 캐시 사전 검사에서 차단되었습니다.** '
                             '0으로 표시된 토큰 합계는 미호출 집계이며, 캐시를 끈 상태에서 실험을 완료했다는 뜻이 아닙니다. '
                             '사유와 근거는 `cache-preflight.json`에 있습니다.']
        if provider_state.get('requests_per_day'):
            detail_lines += ['', f"실제 제공자 한도: 분당 {provider_state.get('requests_per_minute', '미확인')}건 / 하루 {provider_state['requests_per_day']}건."]
        if run_layout.ordered(root):
            detail_lines += ['', '|실험|유형|풀이 조건|추론|계획 분모|형식 통과|숫자 답 없음|',
                             '|---|---|---|---|---:|---:|---:|']
        else:
            detail_lines += ['', '|실험|유형|프롬프트|추론|계획 분모|유효 응답|숫자 비교|숫자 일치|유보 표현 탐지|명시 유보 상태|V5 숫자 답 없음|',
                             '|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|']
        for group in model_summary['groups']:
            prefix = f"|{group['experiment']}|{VARIANT_NAMES.get(group['variant'], group['variant'])}|{group['prompt']}|{group['reasoning']}|{group['planned']}|{group.get('VALID', 0)}|"
            detail_lines.append(prefix + (f"{group.get('numeric_answers_absent', 0)}|" if run_layout.ordered(root) else
                f"{group.get('numeric_compared', 0)}|{group.get('numeric_matches', 0)}|{group.get('abstention_marker_detected', '—')}|{group.get('declared_abstentions', '—')}|{group.get('numeric_answers_absent', '—')}|"))
        write_text((run_layout.validation(root, model['key']) if run_layout.ordered(root) else folder) / 'README.md', run_layout.template(root, 'model-readme-template.md').read_text().format(
            model=model['key'], transport=model['transport'], planned=len(requests), valid=counts['VALID']))
    lines += detail_lines + ['', '## 결과 해석과 비용', '',
              '표는 IC-value-before → IC-value-after → IC-source-before → IC-source-after → IC-relation → EA-01 → EA-02 순서입니다. IC-source before/after는 연결된 value 부모의 위치입니다. A/B는 출처를 부여한 주장 구분이며 원본 유형 ID는 summary.json에 보존합니다. 두 속성을 동일한 효과로 판정하지 않습니다.', '',
              '호출 경로와 사용량은 이 실행의 config.json·시도별 result.json에 기록됩니다. 유료 API·Batch 비용은 반환 토큰과 해당 경로의 단가로 계산한 추정치이며 실제 청구액은 미확인입니다. 사용량이 없는 요청을 0토큰으로 간주하지 않습니다.',
              'V3/V4는 answer의 크기와 negative를 결합하고, V5/V6는 answer 자체의 부호를 그대로 숫자 정답과 비교합니다. scale은 기록하며 다시 곱하지 않습니다. V2는 당시 비교 규칙을 유지합니다. 단위·배율의 의미까지 판정한 정답률은 아닙니다. 명시 유보 상태는 V3/V4 status=abstained의 건수입니다. V5/V6의 숫자 답 없음과 유보의 타당성은 구분하며, 내용 판정은 생성된 02_analysis 자료에서 별도로 확인합니다.',
              '유보 표현 탐지는 응답의 문자열 관찰값입니다. 실험 2의 최종 유보 정확도나 의미 채점으로 사용하지 않습니다. 자동 제작 검사를 통과했다는 사실도 문항이 반드시 답할 수 없다는 증명은 아닙니다. LLM 내용 검토의 실제 진행 상태와 동결 기준은 해당 run의 02_analysis에서 별도로 확인합니다.', '',
              '## 재개와 파일', '',
              f'`PYTHONPATH=src .venv/bin/python -m finarch.experiments.01-evaluation.pipeline run --run {root}`', '',
              '무료 일일·구독 한도에 도달하면 해당 제공자의 실행을 멈춥니다. 한도 복구 후 `--resume-limits`로 재개합니다. 전달 여부를 알 수 없는 요청은 자동 중복 호출하지 않습니다.', '',
              '모델별 `01-requests/manifest.jsonl`은 문항 연결·실험 조건·풀이 입력·prompt·schema를 보존하는 실행 기준입니다. `03-results/results.jsonl`은 실제 응답과 검사, `calls/<문항>/<유형>/<문항>-P0-R-off.json`은 읽기용 요청·응답 묶음, 유형 하위 `_records/<해시>/attempt-xxx`는 시도별 원응답입니다. 새 실행의 선정 순서·제외 사유·출처 확인은 `events.jsonl`의 `INPUT_SELECTION`에 기록합니다.',
              '모델 간 비교는 같은 실행의 입력·프롬프트·추론 설정·호출 경로를 확인해서 해석합니다.']
    if run_layout.ordered(root):
        lines = [line.replace('모델별 `01-requests/manifest.jsonl`', 'E02의 모델별 `manifest.jsonl`')
                 .replace('`03-results/results.jsonl`', '`01_evaluation/04_validation/<model>/results.jsonl`')
                 for line in lines]
        lines += ['', '이 표는 형식·실행 상태를 집계합니다. 원본 숫자 비교는 같은 E04의 numeric-comparisons.jsonl에 기록하고, [A01](../../02_analysis/01_results/README.md)은 저장 응답과 그 평가를 취합합니다. 형식 통과를 정답률로 해석하지 않습니다.']
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
