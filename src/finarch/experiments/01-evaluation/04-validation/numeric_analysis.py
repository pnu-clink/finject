run_layout = __import__('finarch.experiments.90-operations.run_layout', fromlist=['*'])
"""Analyze magnitude-format runs using saved outputs; no evaluator model calls."""
import json
import math
import re
from collections import Counter
from decimal import Decimal
from pathlib import Path
from finarch.paths import SOURCE

read = __import__('finarch.experiments.90-operations.storage', fromlist=['read']).read
rows = __import__('finarch.experiments.90-operations.storage', fromlist=['rows']).rows
write = __import__('finarch.experiments.90-operations.storage', fromlist=['write']).write
write_rows = __import__('finarch.experiments.90-operations.storage', fromlist=['write_rows']).write_rows
write_text = __import__('finarch.experiments.90-operations.storage', fromlist=['write_text']).write_text
now = __import__('finarch.experiments.90-operations.storage', fromlist=['now']).now
event = __import__('finarch.experiments.90-operations.storage', fromlist=['event']).event
VARIANT_NAMES = __import__('finarch.experiments.01-evaluation.04-validation.reporting', fromlist=['VARIANT_NAMES']).VARIANT_NAMES
VARIANT_ORDER = __import__('finarch.experiments.01-evaluation.04-validation.reporting', fromlist=['VARIANT_ORDER']).VARIANT_ORDER
table = __import__('finarch.experiments.02-analysis.legacy.content-analysis.analysis', fromlist=['table']).table
answer_contract = __import__('finarch.experiments.01-evaluation.02-request.answer_contract', fromlist=['*'])


def precision_conflict(request):
    """Recognize explicit literal rounding instructions without inferring intent."""
    question = request['input']['question'].lower()
    words = {word: i for i, word in enumerate(('zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten'))}
    hints = set()
    if 'nearest integer' in question:
        hints.add(0)
    for token in re.findall(r'\b(\d+|zero|one|two|three|four|five|six|seven|eight|nine|ten) decimal places?\b', question):
        hints.add(int(token) if token.isdigit() else words[token])
    supplied = request['input'].get('answer_format', {}).get('decimal_places')
    if hints and hints != {supplied}:
        return {'question_decimal_places': sorted(hints), 'supplied_decimal_places': supplied,
                'policy': 'OBSERVATION_ONLY_NO_REQUEST_OR_SCORE_CHANGE'}
    return None


def response_diagnostics(row, result, reference):
    """Keep diagnostic observations separate from the frozen scoring decision."""
    response = result.get('response')
    observations = []
    for error in result.get('schema_errors', []):
        message = error.get('message', '')
        if message == 'Abstention requires a null answer.':
            observations.append('ABSTAINED_WITH_NUMERIC_ANSWER')
        elif message == 'Abstention requires a null sign.':
            observations.append('ABSTAINED_WITH_BOOLEAN_SIGN')
        elif 'exactly' in message and 'decimal places' in message:
            observations.append('DECIMAL_PLACES_MISMATCH')
        else:
            observations.append('OTHER_SCHEMA_ERROR')
    relaxed = None
    if isinstance(response, dict):
        if response.get('status') == 'abstained':
            observations.append('RAW_STATUS_ABSTAINED')
        meta = response.get('answer_meta', {})
        answer = response.get('answer')
        predicted = None
        if ('status' not in response and 'answer_meta' in response
                and type(answer) in (int, float) and (type(answer) is int or math.isfinite(answer))):
            predicted = Decimal(str(answer))
        elif (response.get('status') == 'answered' and isinstance(answer, str)
              and re.fullmatch(r'(?:0|[1-9][0-9]*)(?:\.[0-9]+)?', answer)
              and type(meta.get('negative')) is bool):
            predicted = Decimal(answer) * (-1 if meta['negative'] else 1)
        if row['experiment'] == 1 and predicted is not None:
            gold = Decimal(reference['reference_answer'])
            if row['status'] != 'VALID':
                relaxed = {'computed': str(predicted), 'gold': str(gold), 'matches': predicted == gold,
                           'policy': 'DIAGNOSTIC_ONLY_IGNORE_REPRESENTATION_PRECISION', 'changes_score': False}
                if predicted == gold:
                    observations.append('INVALID_FORMAT_BUT_EQUAL_NUMERIC_VALUE')
            elif predicted != gold:
                observations.append('SIGN_ONLY_DIFFERENCE' if abs(predicted) == abs(gold) else 'MAGNITUDE_DIFFERENCE')
    return sorted(set(observations)), relaxed


def build(root):
    root = Path(root)
    summary = read(run_layout.validation(root) / 'summary.json')
    private = {x['item_id']: x for x in rows(run_layout.inputs(root) / 'private.jsonl')}
    public = {x['item_id']: x for x in rows(run_layout.inputs(root) / 'public.jsonl')}
    output = run_layout.diagnostics(root)
    output.mkdir(parents=True, exist_ok=True)
    diagnostics = []
    lines = ['# Numerical, sign, and ratio response analysis', '', f"Run {root.name} · The state {summary['status']} • Renewal {now()}", '',
             'This analysis uses stored response, Python test, and source numbers answers to distinguish form error, numeric inconsistency, e-mail declaration, and meaning misrepresentation. Additional evaluation models do not call.', '']
    for model in summary['models']:
        key = model['model']
        entries = rows(run_layout.validation(root, key) / 'results.jsonl')
        requests = {x['trial_id']: x for x in rows(run_layout.requests(root, key))}
        v5 = all(x['response_schema'].get('title') in answer_contract.STRUCTURAL_TITLES for x in requests.values())
        failure_lines = [f'# {key} Failure, inconsistency, original Ubo response', '',
                         'The calculation causes of numerical inconsistencies and the validity of the correct answer and the group interpretation are not automatically verified. Compare the actual question-answer-exam reasoning below.', '']
        local = []
        error_messages = Counter()
        for row in entries:
            result = read(root / row['result_path']) if row.get('result_path') else {}
            checks, response = row.get('checks', {}), result.get('response')
            if run_layout.ordered(root) and row['status'] == 'VALID':
                screen = __import__('finarch.experiments.01-evaluation.04-validation.reporting', fromlist=['screen']).screen
                checks = screen(response, public[row['item_id']], private[row['item_id']])
                row = {**row, 'checks': checks}
            tags = []
            comparison = checks.get('numeric_comparison')
            if row['status'] != 'VALID':
                tags.append(row['status'])
            if comparison:
                tags.append('NUMERIC_MATCH' if comparison['matches'] else 'NUMERIC_MISMATCH')
            if checks.get('declared_abstention'):
                tags.append('DECLARED_ABSTENTION')
            if checks.get('numeric_answer_present') is False:
                tags.append('NUMERIC_ANSWER_ABSENT')
            if row['experiment'] == 1 and not comparison:
                tags.append('BASELINE_NOT_NUMERICALLY_EVALUATED')
            if checks.get('all_quotes_present') is False:
                tags.append('QUOTE_NOT_EXACT_SUBSTRING')
            for error in result.get('schema_errors', []):
                tags.append('SCHEMA_' + str(error['rule']).upper())
            if isinstance(response, dict) and not response.get('evidence'):
                tags.append('EMPTY_EVIDENCE')
            observations, relaxed = response_diagnostics(row, result, private[row['item_id']]['reference'])
            tags.extend(observations)
            conflict = precision_conflict(requests[row['trial_id']])
            if conflict:
                tags.append('QUESTION_METADATA_PRECISION_CONFLICT')
            error_messages.update(error['message'] for error in result.get('schema_errors', []))
            diag = {k: row[k] for k in ('case', 'variant', 'experiment', 'prompt_condition', 'reasoning', 'trial_id', 'status', 'call_path')}
            diag.update(model=key, checks=checks, tags=sorted(set(tags)), numeric_comparison=comparison,
                        diagnostic_numeric_comparison=relaxed, raw_status=response.get('status') if isinstance(response, dict) else None,
                        precision_conflict=conflict,
                        schema_errors=result.get('schema_errors'), usage=result.get('usage'), semantic_assessment='NOT_SCORED')
            local.append(diag)
            if row['status'] not in ('VALID', 'NOT_RUN') or 'NUMERIC_MISMATCH' in tags or (row['experiment'] == 1 and 'DECLARED_ABSTENTION' in tags):
                failure_lines += [f"## {row['case']} · {VARIANT_NAMES.get(row['variant'],row['variant'])} · {row['prompt_condition']}/{row['reasoning']}", '',
                    f"State of play: {row['status']} · Classification: {', '.join(tags)}", '',
                    f"[Request and Answer JSON]{'../../' if run_layout.ordered(root) else '../'}{row['call_path']})" if row.get('call_path') else 'No saved calls', '',
                    '**The question is:** ' + public[row['item_id']]['question'], '',
                    '**The real delivery text:** ' + public[row['item_id']]['context'], '',
                    '**The source numbers is the right answer:** ' + str(private[row['item_id']]['reference']['reference_answer']) + ' (Not using the meaning of the variable as the correct answer)', '',
                    '```json', json.dumps({'response': response, 'schema_errors': result.get('schema_errors'), 'comparison': comparison, 'diagnostic_comparison_only': relaxed, 'error': result.get('error')}, ensure_ascii=False, indent=2), '```', '']
        diagnostics.extend(local)
        write_text(output / f'{key}-failures.md', '\n'.join(failure_lines))
        lines += [f'## {key}', '', f"The plan. {model['planned']}entries · attempts {model['attempts']}Circular state {model['statuses']}", '',
                  f"Input tokens {model['input_tokens']:,}Cache, please enter. {model['cache_read_tokens']:,}The output token. {model['output_tokens_including_thinking']:,}The call path is `{model['transport']}` and differentiate between the cost of a Codex subscription and the cost of an API.", '', '♪ The original problem ♪', '']
        data = []
        for prompt, reasoning in sorted({(x['prompt_condition'], x['reasoning']) for x in local if x['experiment'] == 1}):
            subset = [x for x in local if x['experiment'] == 1 and x['prompt_condition'] == prompt and x['reasoning'] == reasoning]
            compared = [x for x in subset if x['numeric_comparison'] is not None]
            matched = sum(x['numeric_comparison']['matches'] for x in compared)
            data.append([run_layout.prompt_label(prompt), reasoning, len(subset), sum(x['status'] == 'VALID' for x in subset), len(compared), matched,
                         sum(not x['numeric_comparison']['matches'] for x in compared),
                         'Not evaluated' if v5 else sum('DECLARED_ABSTENTION' in x['tags'] for x in subset),
                         f'{matched / len(subset):.1%}' if subset else '—',
                         f'{matched / len(compared):.1%}' if compared else '—'])
        lines += table(['Solving condition', 'The conditions of inference', 'The plan.', 'Format valid', 'Numeric comparison', 'Numeric match', 'Numeric mismatch', 'Available for you.', 'It\'s a match for the plan.', 'Compare my response to the'], data)
        lines += ['The plan-to-plan unit is a fixed denominator, including undervaluation and form failure. The ratio of comparable responses is a conditional observation, and it\'s not used as a total correct answer.', '']
        lines += ['♪ ♪ The problem of transformation ♪', '']
        groups = []
        for variant in list(VARIANT_ORDER)[1:]:
            for prompt in sorted({x['prompt_condition'] for x in local}):
                for reasoning in sorted({x['reasoning'] for x in local}):
                    subset = [x for x in local if x['variant'] == variant and x['prompt_condition'] == prompt and x['reasoning'] == reasoning]
                    groups.append([VARIANT_NAMES[variant], run_layout.prompt_label(prompt), reasoning, len(subset),
                                   sum(x['status'] == 'VALID' for x in subset),
                                   'Not evaluated' if v5 else sum('DECLARED_ABSTENTION' in x['tags'] for x in subset),
                                   'Not applicable' if v5 else sum('RAW_STATUS_ABSTAINED' in x['tags'] and x['status'] != 'VALID' for x in subset)])
        lines += table(['Type', 'Prompt', 'The conditions of inference', 'The plan.', 'Format valid', 'Available for you.', 'I\'ve written a few books, but I\'m not a good fit.'], groups)
        lines += ['Failure and testing observations', '']
        counts = Counter(tag for x in local for tag in x['tags'])
        lines += table(['Classification', 'Count'], sorted(counts.items()))
        lines += ['You can tag multiple responses. `RAW_STATUS_ABSTAINED`The raw response observation value, including the format failure, is no longer valid in the UBO. `INVALID_FORMAT_BUT_EQUAL_NUMERIC_VALUE`When the numerical form is ignored, the same number results in the same diagnosis, which does not change the original failure judgment.', '']
        lines += table(['The real reason for the failure of the test', 'The frequency of occurrence'], error_messages.most_common())
        conflicts = [x for x in local if x['precision_conflict']]
        conflict_cases = {x['case']: x for x in conflicts if x['experiment'] == 1}
        lines += ['#### Conflict between questions and minority metadata', '',
                  f"The metadata that is being conveyed is that the expressive digit phrases and metadata are being conveying to other sources. {len(conflict_cases)}It\x27s a items, and the request is {len(conflicts)}entries (original {sum(x['experiment'] == 1 for x in conflicts)}entries, variants {sum(x['experiment'] == 2 for x in conflicts)}The number of digits left in the original reference answer and the number of digitals that the question asked for are different concepts. Below is the observation value of the actual request that was sent and no automatic correction or score changes.", '']
        lines += table(['Source text', 'Question number', 'The metadata is transmitted digitally.'],
                       [[case, x['precision_conflict']['question_decimal_places'], x['precision_conflict']['supplied_decimal_places']]
                        for case, x in sorted(conflict_cases.items())])
        write_rows(output / f'{key}-precision-conflicts.jsonl', conflicts)
        samples = rows(run_layout.execution(root, key) / 'resources.jsonl')
        if samples:
            resource = {'samples': len(samples), 'maximum_active': max(s['active'] for s in samples),
                        'maximum_limit': max(s['concurrency_limit'] for s in samples),
                        'maximum_cpu_percent': max(s['cpu_percent'] for s in samples),
                        'maximum_memory_percent': max(s['memory_percent'] for s in samples),
                        'minimum_available_memory_gb': min(s['available_memory_bytes'] for s in samples) / 1024 ** 3,
                        'memory_blocked_samples': sum(s['memory_blocked'] for s in samples)}
            write(output / f'{key}-resources.json', resource)
            lines += ['### Use the resources', '', '```json', json.dumps(resource, indent=2), '```', '']
        lines += [f'[Failure: numerical inconsistency details]{key}-failures.md)' if run_layout.ordered(root) else f'[Failure: numerical inequality detail]{key}-failures.md)', '']
    lines += ['♪ The range of interpretation ♪', '',
              'The numerical units of V5 (including V7) directly compare the answer number itself with the original reference answer. They apply the same symbol as the previous V3 and V40,000 agreements. The differential does not multiply again. It does not confirm the correctness of the entire process of computation, communication, unit meaning.',
              'The status=abstained of V3·V4 and the classification of V7 are declarations returned by the model. NUMERIC_ANSWER_ABSENT only records no numerical answers, and does not confirm the appropriateness of the e-books in this numerical test.1 Content review and A02 And we\'re seeing from the comparison results that you don\'t combine the form failure with the original e-mail as a miscalculation.',
              'Luna\'s none/medium and Gemini\'s thinking budget off/on are different controls. Switching from CLI to API also changes the basic instruction and transmission mode. You can\'t determine the difference from previous executions by a single caching or response format change effect.', '']
    write_rows(output / 'response-diagnostics.jsonl', diagnostics)
    write_text((run_layout.diagnostics(root) / 'numeric-analysis.md') if run_layout.ordered(root) else root / 'ANALYSIS.md', '\n'.join(lines))
    if run_layout.ordered(root):
        render = __import__('finarch.experiments.02-analysis.legacy.content-analysis.semantic_review', fromlist=['render_readme']).render_readme
        render(root)
    else:
        write_text(output / 'README.md', (SOURCE / 'experiments/templates/numeric-analysis-readme-template.md').read_text())
    event(root, 'NUMERIC_ANALYSIS_COMPLETED', records=len(diagnostics), new_model_calls=0)
