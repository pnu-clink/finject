"""E02: freeze prompts, response schema, request manifests and the request plan."""
import json
import math
import random
import shutil
from pathlib import Path
from finarch.paths import SOURCE
from finarch.experiments import assets

store = __import__('finarch.experiments.90-operations.storage', fromlist=['*'])
run_layout = __import__('finarch.experiments.90-operations.run_layout', fromlist=['*'])
answer_format = __import__('finarch.experiments.01-evaluation.04-validation.answer_format', fromlist=['*'])
cache_policy = __import__('finarch.experiments.01-evaluation.02-request.cache_policy', fromlist=['*'])
call_layout = __import__('finarch.experiments.01-evaluation.03-execution.call_layout', fromlist=['*'])
request_order = __import__('finarch.experiments.01-evaluation.02-request.request_order', fromlist=['*'])
providers = __import__('finarch.experiments.01-evaluation.03-execution.providers', fromlist=['*'])
PROJECT, read, write, write_rows, digest, now = store.PROJECT, store.read, store.write, store.write_rows, store.digest, store.now


def prepare(root, config, public, selection, prior_definition=None):
    ordered_layout = run_layout.ordered(root)
    items = selection['items']
    definition = run_layout.definition(root)
    definition.mkdir(parents=True, exist_ok=True)
    previous = run_layout.definition(prior_definition) if prior_definition else None
    shutil.copyfile(previous / 'response.schema.json' if previous else assets.schema_path('solver_response'),
                    definition / 'response.schema.json')
    shutil.copyfile(previous / 'common.md' if previous else assets.prompt_path('solver_common'),
                    definition / 'common.md')
    for condition, name in run_layout.PROMPT_FILES.items():
        origin = (run_layout.prompt_file(previous, condition) if previous else
                  assets.prompt_path('solver_' + condition))
        shutil.copyfile(origin, definition / name)
    for name in ('run-readme-template.md', 'model-readme-template.md'):
        template_source = SOURCE / 'experiments/templates' / ('ordered-' + name if ordered_layout else name)
        target = run_layout.preparation(root) / name if ordered_layout else definition / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(template_source, target)
    schema = read(definition / 'response.schema.json')
    if config.get('response_contract') and schema.get('title') != config['response_contract']:
        raise ValueError('RESPONSE_CONTRACT_VERSION_MISMATCH')
    common = (definition / 'common.md').read_text()
    prompts = {condition: common + '\n' + run_layout.prompt_file(definition, condition).read_text()
               for condition in run_layout.PROMPT_FILES}
    inputs = {p['item_id']: p for p in public}
    plan = {'created_at': now(), 'models': [], 'source': config['dataset'],
            'cache_policy': cache_policy.snapshot(),
            'concurrency': config['schedule'].get('concurrency'), 'paid_api_fallback': False,
            'transport': 'NATIVE_ANTHROPIC_MESSAGE_BATCHES_API' if any(m['transport'] == 'anthropic_batch' for m in config['models']) else 'NATIVE_OPENAI_BATCH_API' if any(m['transport'] == 'openai_batch' for m in config['models']) else 'NATIVE_GEMINI_BATCH_API' if any(m['transport'] == 'gemini_batch' for m in config['models']) else 'PYTHON_MANAGED_REQUEST_GROUPS', 'native_provider_batch_api': any(m['transport'] in ('gemini_batch', 'openai_batch', 'anthropic_batch') for m in config['models']),
            'semantic_evaluator_calls': 0, 'actual_billed_cost_usd': None}
    for model in config['models']:
        trials = []
        for item in items:
            for prompt in run_layout.PROMPT_FILES:
                for reasoning in config['reasoning_modes']:
                    trial = {k: item[k] for k in ('item_id', 'case', 'experiment', 'variant')}
                    trial.update(model=model['model'], prompt_condition=prompt, reasoning=reasoning,
                                 cache_policy=cache_policy.snapshot(),
                                 prompt=prompts[prompt], response_schema=schema,
                                 input=answer_format.model_input(inputs[item['item_id']], schema),
                                 max_output_tokens=model.get('output_limits', {}).get(reasoning, config.get('max_output_tokens')))
                    if model.get('model') in ('gemini-3.8-flash', 'gemini-3.5-flash-lite'):
                        trial['thinking_level'] = model['thinking_levels'][reasoning]
                    elif model.get('model') == 'claude-haiku-5-5':
                        trial['reasoning_effort'] = model['reasoning_efforts'][reasoning]
                        trial['thinking_type'] = 'adaptive' if reasoning == 'on' else 'disabled'
                    elif model['transport'] not in ('codex_cli', 'openai_responses', 'openai_batch', 'orca_api'):
                        trial['thinking_budget'] = model.get('thinking_budget', config.get('thinking_budget'))
                    if type(trial['max_output_tokens']) is not int or trial['max_output_tokens'] < 1:
                        raise ValueError('POSITIVE_MAX_OUTPUT_TOKENS_REQUIRED')
                    if model['transport'] in ('codex_cli', 'openai_responses', 'openai_batch', 'orca_api'):
                        trial['reasoning_effort'] = model['reasoning_efforts'][reasoning]
                    trial['trial_id'] = digest({'request': trial, 'transport': model['transport']})[:32]
                    providers.validate_request(trial)
                    trials.append(trial)
        random.Random(config['seed']).shuffle(trials)
        trials.sort(key=lambda t: t['experiment'])
        trials = request_order.prioritize_pilot(trials, config.get('improvement', {}).get('pilot_cases'))
        if model['transport'] in ('codex_cli', 'openai_responses', 'orca_api'):
            probes = [next(t for t in trials if t['experiment'] == 1 and t['reasoning'] == mode) for mode in config['reasoning_modes']]
            trials = probes + [t for t in trials if t not in probes]
        folder = run_layout.requests(root, model['key']).parent
        call_layout.check_manifest(run_layout.execution(root, model['key']), trials)
        write_rows(folder / 'manifest.jsonl', trials)
        approx = sum(math.ceil((len(t['prompt']) + len(json.dumps(t['input'])) + len(json.dumps(schema))) / 4) for t in trials)
        rates = model.get('reference_price_per_million')
        if model['transport'] in ('openai_responses', 'openai_batch'):
            rates = __import__('finarch.experiments.01-evaluation.03-execution.openai_api', fromlist=['accounting']).accounting(model)[0]
        plan['models'].append({'key': model['key'], 'model': model['model'], 'transport': model['transport'],
            'requests': len(trials), 'experiment1': sum(t['experiment'] == 1 for t in trials),
            'experiment2': sum(t['experiment'] == 2 for t in trials),
            'input_token_estimate': approx, 'estimate_method': 'CHARACTERS_DIVIDED_BY_FOUR_NOT_TOKENIZER',
            'api_equivalent_estimate_usd_at_1000_output_tokens': (approx * rates['input'] + len(trials) * 1000 * rates['output']) / 1e6 if rates else None,
            'incremental_api_charge_usd': 0 if model['transport'] == 'codex_cli' else None,
            'billed_estimate': 'PAID_BATCH_USAGE_ESTIMATE_NOT_INVOICE' if model['transport'] in ('gemini_batch', 'openai_batch', 'anthropic_batch') else
                              'PAID_PROVIDER_STANDARD_API_ESTIMATE_NOT_INVOICE' if model['transport'] in ('anthropic_api', 'gemini_paid_api', 'orca_api') else
                              'PAID_OPENAI_STANDARD_API_USAGE_ESTIMATE_NOT_INVOICE' if model['transport'] == 'openai_responses' else
                              'FREE_KEY_OR_INCLUDED_SUBSCRIPTION_REQUESTED_NO_PAID_FALLBACK'})
    write(run_layout.plan(root), plan)
    return plan
