"""Resume the authorized native-Batch study without choosing unreviewed changes."""
import argparse
from collections import Counter
import json
from pathlib import Path
from finarch.experiments import assets

store = __import__('finarch.experiments.90-operations.storage', fromlist=['*'])
pipeline = __import__('finarch.experiments.01-evaluation.pipeline', fromlist=['*'])
semantic = __import__('finarch.experiments.02-analysis.legacy.content-analysis.semantic_review', fromlist=['*'])
CAMPAIGN = '20260927-luna-three-rounds'
REPORT = store.PROJECT / 'reports/run' / CAMPAIGN
BEGIN, END = '<!-- LUNA-THREE-ROUNDS:BEGIN -->', '<!-- LUNA-THREE-ROUNDS:END -->'
VARIANT_ORDER = ('ORIGINAL', 'IC_VALUE_01_BEFORE', 'IC_VALUE_01_AFTER', 'IC_SOURCE_A_ONLY', 'IC_SOURCE_B_ONLY', 'IC_RELATION_01', 'EA_01', 'EA_02')


def runs():
    found = []
    for path in (store.PROJECT / 'reports/experiments-run').glob('*/config.json'):
        config = store.read(path)
        if config.get('improvement', {}).get('campaign') == CAMPAIGN:
            found.append((config['improvement']['round'], path.parent, config))
    found.sort()
    if len({r[0] for r in found}) != len(found):
        raise ValueError('DUPLICATE_CAMPAIGN_ROUND')
    return found


def costs(root):
    summary = store.read(root / 'summary.json', {})
    models = summary.get('models', [])
    solver = sum(m.get('paid_batch_usage_cost_estimate_usd') or 0 for m in models)
    analysis = sum(store.read(p).get('token_cost_estimate_usd') or 0 for p in (root / semantic.ROOT).rglob('state.json'))
    missing = sum(m.get('attempts_without_usage') or 0 for m in models)
    missing += sum(store.read(p).get('requests_without_known_cost') or 0 for p in (root / semantic.ROOT).rglob('state.json'))
    return {'solver': solver, 'analysis': analysis, 'total': solver + analysis, 'unknown_cost_records': missing}


def repeat_controls(first, second):
    """Describe unchanged-request variation separately from prompt revisions."""
    model_a = store.read(first / 'config.json')['models'][0]['key']
    model_b = store.read(second / 'config.json')['models'][0]['key']
    identity = lambda r: (r['case'], r['variant'], r['prompt_condition'], r['reasoning'])
    requests = [{identity(r): r for r in store.rows(root / key / '01-requests/manifest.jsonl')} for root, key in ((first, model_a), (second, model_b))]
    results = [{identity(r): r for r in store.rows(root / key / '03-results/results.jsonl')} for root, key in ((first, model_a), (second, model_b))]
    groups = {}
    for key in sorted(set(requests[0]) & set(requests[1])):
        group = groups.setdefault(key[2], Counter())
        a, b = requests[0][key], requests[1][key]
        identical = all(a.get(field) == b.get(field) for field in ('model', 'input', 'prompt', 'response_schema', 'reasoning_effort', 'max_output_tokens'))
        group['same_request' if identical else 'changed_request'] += 1
        ra, rb = results[0].get(key), results[1].get(key)
        if not identical:
            continue
        if not ra or not rb or ra['status'] != 'VALID' or rb['status'] != 'VALID':
            group['unassessed'] += 1
            continue
        group['comparable'] += 1
        aa, ab = ra['response']['answer'], rb['response']['answer']
        group['number_null_transition'] += (aa is None) != (ab is None)
        group['answer_changed'] += aa != ab
    return groups


def round_pairs(first, second):
    """Compare only jointly assessed responses; retain all planned pairs."""
    folders = [Path(root) / '02_analysis/02_comparison/rows.jsonl' for root in (first, second)]
    if not all(folder.exists() for folder in folders):
        return []
    rows = [{**row, 'round': label} for label, folder in zip(('previous', 'next'), folders) for row in store.rows(folder)]
    return [{**semantic.paired([r for r in rows if r['prompt_condition'] == prompt and r['reasoning'] == reasoning], 'round', 'previous', 'next'),
             'prompt': prompt, 'reasoning': reasoning} for prompt in ('P0', 'P1') for reasoning in ('off', 'on')]


def write_report():
    REPORT.mkdir(parents=True, exist_ok=True)
    cohort = runs()
    cost_lines, sections, paper_lines, outcome_lines = [], [], [], []
    reviewed_rounds = 0
    total_costs = Counter()
    for number, root, config in cohort:
        state, summary = store.read(root / 'state.json'), store.read(root / 'summary.json')
        analyzed = store.read(root / '02_analysis/02_comparison/summary.json')
        model = summary['models'][0]
        cost = costs(root)
        total_costs.update(cost)
        reviews = [event for event in store.rows(root / 'events.jsonl') if event.get('event') == 'STUDY_CRITICAL_REVIEW']
        reviewed_rounds += bool(analyzed and reviews)
        status = 'Critical review and paper revision' if analyzed and reviews else 'Content analysis aggregated \xb7 critical review pending' if analyzed else 'Analysis in progress' if state['status'] == 'FINISHED' else state['status']
        cost_lines.append(f"|{number}The car {root.name}|{status}|${cost['solver']:.6f}|${cost['analysis']:.6f}|${cost['total']:.6f}|{cost['unknown_cost_records']}|")
        sections.extend([f'## {number}The car {root.name}', '',
            f'[See on the viewer]http://127.0.0.1:8894/?run={root.name}And then I\x27m going to start the experiment.{root.name}/README.md)', '',
            f"- The condition: {state['status']}The format {model.get('statuses', {})}; cache {model.get('cache_verification', {}).get('status', 'Unconfirmed')}.",
            f"- Prompt: What is it? {config['improvement'].get('prompt_revision', 'Not recorded')}The output is low. {config['max_output_tokens']}tokens.", ''])
        note = config['improvement'].get('review_of_previous_round')
        if note:
            sections += ['#### Forward-facing review and this change', '', note, '']
        groups = [g for g in model.get('groups', []) if g['experiment'] == 1]
        originals_by_reasoning = {g['reasoning']: g for g in groups}
        original_digest = ' · '.join(f"{reasoning.upper()} {originals_by_reasoning[reasoning].get('numeric_matches', 0)}/100"
            if originals_by_reasoning.get(reasoning, {}).get('numeric_compared') else f'{reasoning.upper()} Not evaluated' for reasoning in ('off', 'on'))
        variant_digest = []
        for prompt in ('P0', 'P1'):
            for reasoning in ('off', 'on'):
                cells = [c for c in analyzed.get('matrix', []) if c['variant'] != 'ORIGINAL' and c['prompt'] == prompt and c['reasoning'] == reasoning] if analyzed else []
                variant_digest.append(f"{sum(c['appropriate'] for c in cells)}/{sum(c['assessed'] for c in cells)}" if cells else 'Analysis in progress')
        mode_digest = f"{analyzed['overall'].get('p1_mode_answer_mismatches', 0)}/{analyzed['overall'].get('p1_mode_answer_checked', 0)}" if analyzed else 'We\'re waiting for the assembly.'
        outcome_lines.append(f"|[{number}The car]http://127.0.0.1:8894/?run={root.name}&tab=analysis)|{original_digest}|" + '|'.join(variant_digest) + f'|{mode_digest}|')
        sections += ['The source code is the condition of the number of the plan/number of the plan.', '|---|---:|---:|---:|']
        for g in groups:
            observed = g.get('numeric_compared', 0) + g.get('numeric_answers_absent', 0)
            match = f"{g.get('numeric_matches', 0)} / {g['planned']}" if observed else f"Not evaluated / {g['planned']}"
            sections.append(f"|P0 · {g['reasoning']}|{match}|{g.get('numeric_compared', 0)}|{g.get('numeric_answers_absent', 0)}|")
        sections.append('')
        if number > 1:
            sections += [f"- The probability of input is {cohort[0][1].name}The same as 800The case case trial and failure records are commonly used. 0."]
        stage_states = [(str(p.parent.relative_to(root / semantic.ROOT)), store.read(p)) for p in sorted((root / semantic.ROOT).rglob('state.json'))]
        sections += [f"- The analysis. {name}: {s['status']} · {s.get('statuses', s.get('request_counts', {}))}" for name, s in stage_states]
        sections.append('')
        if analyzed:
            a = analyzed['overall']
            bounds = ' ~ '.join(f'{100 * b:.1f}%' for b in a['planned_worst_best_bounds'])
            sections += [f"The content is judged. {a['assessed']}/{a['planned']}The right answer. {a['appropriate']}/{a['assessed']}I\x27m not going to say. {a['unassessed']}Re-examination of inconsistency {a['audit_disagreements']}The range of times that all the non-precise responses in the whole plan denominator are either inappropriate or not is the range of times the whole plan is in the same order. {bounds}And that\x27s a range that depends on the validity of the analytical judgment.", '',
                'The design of the project is based on the design of the design of a project.', '|---|---|---|---:|---:|---:|']
            for c in sorted(analyzed['matrix'], key=lambda c: (VARIANT_ORDER.index(c['variant']), c['prompt'], c['reasoning'])):
                sections.append(f"|{c['variant']}|{c['prompt']}|{c['reasoning']}|{c['format_valid']}/{c['planned']}|{c['appropriate']}/{c['assessed']}|{c['unassessed']}|")
            sections += ['', f"Reviewed {a['audit_reviewed']}The big difference in judgments of appropriate/inappropriate/irreconcilable responses is that the response is not a good one. {a['audit_appropriateness_disagreements']}It\x27s a items. It\x27s strictly inconsistent, including the type of error, the calculation, the computation, the consistency. {a['audit_disagreements']}And they\x27re all preserved in the basic set of unresolved, and the sample is chosen judgementally, so we don\x27t interpret this as the total error rate.", '']
            sections += ['', 'Compare the two to the two. 0→1| Deterioration 1→0The rate difference is.', '|---|---:|---:|---:|---:|']
            for p in analyzed['paired']:
                difference = 'Not evaluated' if p['difference'] is None else f"{100 * p['difference']:+.1f}%p"
                sections.append(f"|{p['left']}→{p['right']} · {' '.join(p.get('fixed_conditions', {}).values())}|{p['assessed_pairs']}/{p['planned_pairs']}|{p['transitions'].get('0->1', 0)}|{p['transitions'].get('1->0', 0)}|{difference}|")
            sections += ['', 'P1 Conjecture Conditionally Conforming / Input Conforming/ Possible Conforming Conforming: Conditionally Subject to Conforming', '|---|---:|---:|---:|---:|']
            for reasoning in ('off', 'on'):
                cells = [c for c in analyzed['matrix'] if c['prompt'] == 'P1' and c['reasoning'] == reasoning]
                modes = ' / '.join(str(sum(c.get('p1_stated_modes', {}).get(mode, 0) for c in cells)) for mode in ('ANSWER', 'CONDITIONAL', 'ABSTAIN'))
                contradiction = f"{sum(c.get('p1_mode_answer_mismatches', 0) for c in cells)} / {sum(c.get('p1_mode_answer_checked', 0) for c in cells)}"
                behavior = f"{sum(c.get('p1_mode_behavior_mismatches', 0) for c in cells)} / {sum(c.get('p1_mode_behavior_compared', 0) for c in cells)}"
                sections.append(f"|{reasoning}|{sum(c['p1_classification_matches'] for c in cells)} / {sum(c['p1_classification_compared'] for c in cells)}|{modes}|{contradiction}|{behavior}|")
            sections += ['', 'Declaration-digit/null contradiction is ANSWER, and null or CONDITIONAL/ABSTAIN is a local test for a number case. Declaration-control behavior inconsistency analysis LLM read behavior and declaration in other cases, including the possibility of error by the analyst. These statements have been added without slightly changing the existing form-and-meaning scores.']
            sections += ['', 'P1 Reasoning and Conditions Department Statement / Requesting and Analysing of the Conditions Observed by the Analyst / Reviewing the Conditions of the Required Conditions', '|---|---:|---:|---:|']
            for reasoning in ('off', 'on'):
                cells = [c for c in analyzed['matrix'] if c['prompt'] == 'P1' and c['reasoning'] == reasoning]
                mode = lambda field: sum(c.get(field, {}).get('CONDITIONAL', 0) for c in cells)
                sections.append(f"|{reasoning}|{mode('p1_stated_modes')} / {sum(c['p1_planned'] for c in cells)}|{mode('observed_behaviors')} / {sum(c.get('p1_mode_behavior_compared', 0) for c in cells)}|{mode('appropriate_behaviors')}|")
            sections += ['', 'The number declared as conditional distinguishes from the behavior observed by the analyst in the description. A valid conditional is a provisional judgment, except for the inconsistency of the unresolved and re-evaluated, and the result per conditional is not its own statistic or a completely objective indicator of the quantity of information. It also leaves the possibility that the classification statement influenced the judgment of the behavior.']
            sections += ['', 'Critical interpretation and the next step', '',
                f"Reverse case of original and transformation response {analyzed['counterexample_count']} `02_analysis/02_comparison/counterexamples.jsonl`It\x27s a case of whether the source numbers matching doesn\x27t guarantee the validity of the variation, and whether the source numbers are wrong and correspond to the conflict and resolution of the variance.", '',
                'The judgments of the analytical LLM are default values, and we need to review the shared errors of the same Luna array, the selection bias of the verifiable response alone, the input judgment error, and the reassessment inconsistency together, not interpreting the null increase itself as an improvement.', '']
            if reviews:
                sections += [reviews[-1]['report_ko'], '']
            paper_lines.append(f"|{number}rounds |{root.name}|{model['statuses'].get('VALID', 0)}/3000|{a['assessed']}/3000|{a['appropriate']}/{a['assessed']}|{a['unassessed']}|${cost['total']:.6f}|")
    cost_lines.append(f"The total amount of use is $$$$${total_costs['solver']:.6f}|${total_costs['analysis']:.6f}|${total_costs['total']:.6f}|{total_costs['unknown_cost_records']}|")
    if len(cohort) > 1:
        comparisons = list(zip(cohort, cohort[1:]))
        if len(cohort) == 3:
            comparisons.append((cohort[0], cohort[2]))
        sections += ['## Variable of the same request between variables', '', 'The difference between requests to change the P1 instruction is an improvement experiment, where the actual payload identifies only the same request separately, and records the number/null shift and the variation of the response. The same model name doesn\'t guarantee even a fixed internal version of the provider.', '',
            'The number of times the number of times a month is changed is the number of days the number of years the number of months the number of weeks is changed is changed is called the number of hours the number of minutes the number of the month is changed', '|---|---|---:|---:|---:|---:|---:|---:|']
        for a, b in comparisons:
            for prompt, counts in repeat_controls(a[1], b[1]).items():
                sections.append(f"|{a[0]}→{b[0]}rounds |{prompt}|{counts['same_request']}|{counts['changed_request']}|{counts['comparable']}|{counts['number_null_transition']}|{counts['answer_changed']}|{counts['unassessed']}|")
        sections.append('')
        sections += ['### Comparison of the content of the judgments between the variables', '', 'We compare the same response conditions that can be determined by both variables. 800Pair/reference condition, P1 is the transformation 700It\'s a pair/reference condition so we don\'t see the denominator of two rows as equal, and we don\'s identify the natural variation of the missing pair and P0 together, and we\'re not interpreting the whole of the P1 change as the side effect of the directional improvement.', '',
            'The two-way conditions are determined by the plan. 0→1| Deterioration 1→0The rate difference is.', '|---|---|---:|---:|---:|---:|']
        for a, b in comparisons:
            for p in round_pairs(a[1], b[1]):
                difference = 'Not evaluated' if p['difference'] is None else f"{100 * p['difference']:+.1f}%p"
                sections.append(f"|{a[0]}→{b[0]}rounds |{p['prompt']} · {p['reasoning']}|{p['assessed_pairs']}/{p['planned_pairs']}|{p['transitions'].get('0->1', 0)}|{p['transitions'].get('1->0', 0)}|{difference}|")
        sections.append('')
    template = (store.PROJECT / 'src/finarch/experiments/templates/three-rounds-report.md').read_text()
    completion = '3The results of the analysis, the review, the analysis, and the analysis are completed. The undervalued and underresolved responses are stored in the denominator below.' if reviewed_rounds == 3 else f'In progress. Critical review and reflection of the debate. {reviewed_rounds}/3round'
    if any(event.get('event') == 'USER_REVIEW_RESET' for event in store.rows(REPORT / 'events.jsonl')):
        completion = 'Modification of the progress method · Conventional API analysis; backup of the progress conclusions. 1The raw response is reviewed directly by Codex and the user agrees on the improvements. 2·3The data from the car and API analysis is the previous execution efficiency.'
    delivery = [event for event in store.rows(REPORT / 'events.jsonl') if event.get('event') == 'STUDY_DELIVERY_VERIFIED']
    verification = delivery[-1]['report_ko'] if delivery else 'It\'s before the actual screen and the final integrity check.'
    text = template.replace('{{updated}}', store.now()).replace('{{completion}}', completion).replace('{{verification}}', verification).replace('{{costs}}', '\n'.join(cost_lines)).replace('{{outcomes}}', '\n'.join(outcome_lines)).replace('{{rounds}}', '\n'.join(sections))
    store.write_text(REPORT / 'README.md', text)
    return paper_lines


def update_paper():
    """Replace only the explicitly marked development-study block."""
    if any(event.get('event') == 'USER_REVIEW_RESET' for event in store.rows(REPORT / 'events.jsonl')):
        write_report()
        return False
    paper = store.PROJECT / 'reports/run/20260924-paper-draft/PAPER-KO.md'
    text = paper.read_text()
    rows = write_report()
    if not rows:
        return False
    findings = []
    for number, root, _ in runs():
        reviews = [event for event in store.rows(root / 'events.jsonl') if event.get('event') == 'STUDY_CRITICAL_REVIEW']
        if reviews and reviews[-1].get('paper_ko'):
            findings.extend([f'#### {number}The limits of observation and interpretation of the car', '', reviews[-1]['paper_ko'], ''])
    block = '\n'.join([BEGIN, '### 8.1 Same 100The original. 3The experiment in car development.', '',
        'Same code. 100and 7Variations of the species 700Keeping the items and GPT-6-Luna was run as OpenAI Batch API. The original version was P0×Reasoning OFF/ON, the modification was P0/P1×Reasoned OFF/On 3,000The reasoning setting was none/medium, and the cache was deactivated without breakpoint in the specified mode. The modified prompt and the unchanged condition were integrated into the variable request manifest.', '',
        'The object. 20260917-002The first one that passed both the initial preparation and the automatic checks of the seven variations in the order of the results 100It\'s the basic. 20items, the modification set is incomplete. 159It\'s not a random sample, it\'s a selected sample. 100items\' human judgement records are PENDING. Therefore, the selection bias and human mismatch status according to the conditions of completion of the production are preserved and are not generalized to the entire dataset.', '',
        'The answering possibilities of input were first examined by the pool as an analysis LLM that did not see the response; the product type; gold; and the same judgments were used as a common criterion among the variables. Later, the model-condition identifier-based responses were reviewed separately as computation, approximation, consistency, action, distribution compliance. The answering phrases of P1 can be guessed as the content of the conditions, so that the full condition is not obscured. 8The items response was reviewed and preserved as a nonconforming misconception. This re-evaluation is not a random estimate of the total assessment error rate, so it refers to the same input judgment and does not exclude errors that are shared with the input judgment.', '',
        'The data is available in the form of a log, a log, an account, a log file, a log entry, a log log entry, an accounting account, a data entry, a data transfer, a data recovery, a data collection, a data analysis, a data management system, a data processing system, a database, a data analytics system, a computer system, a system of data processing, a data security system, a log data analytics, a data control system, a documentation system, a file system, a recording system, a reporting system, an account analytics system and a data analytical system, a process analytics system.', '|---|---|---:|---:|---:|---:|---:|', *rows, '',
        *findings,
        'The above semantic assessment does not mean independent gold or human final verification as the results of the same Luna array analysis. The dependencies of the seven variations per element are preserved and compared correspondingly, while the form failure, failure to solve, failure to analyze, and the denominator of the misconception are preserved. The original P1 normal counterparts cannot generalize the excessive euphoricity of P1 in normal problems without this range. The close inter-dimensional changes in the same data are the result of exploratory development and are not used as independent verification. Repeated variations report the request payloads only under the same conditions in fact separately, distinguishing them from improvements in the modified P1.', '',
        '[Cross-disclosure conditions, judgment, half-discovery, cost records](../20260927-luna-three-rounds/README.md)', END])
    block = block.replace('P0', 'Unguided Solving').replace('P1', 'Criteria-Guided Solving')
    if BEGIN in text:
        before, rest = text.split(BEGIN, 1)
        _, after = rest.split(END, 1)
        revised = before + block + after
    else:
        marker = '## 8. \uc2e4\ud5d8 \uacb0\uacfc\n'
        if marker not in text:
            raise ValueError('PAPER_RESULTS_SECTION_NOT_FOUND')
        revised = text.replace(marker, marker + '\n' + block + '\n', 1)
    revised = revised.replace('\uc2e4\ud5d8 \uacb0\uacfc\uc640 \uacb0\ub860\uc740 \uacf5\ub780\uc785\ub2c8\ub2e4.', '8.1The scrapbook records actual collected development experiments and preliminary analysis, but the final verification experiments and conclusions are not yet complete.')
    revised = revised.replace('\uc544\ub798\ub294 2026-09-26\uc5d0 \ud655\uc778\ud55c \ud604\ud589 \uc791\uc5c5 \ud30c\uc77c\uc758 \ub0b4\uc6a9\uc774\uba70, \ucd5c\uc885 \uc2e4\ud5d8\uc5d0 \uc0ac\uc6a9\ud55c \ubc84\uc804\uc740 \ud574\ub2f9 \uc2e4\ud589\uc758 \ub3d9\uacb0 \ud30c\uc77c·\ud574\uc2dc\uc640 \ub300\uc870\ud558\uc5ec \ud655\uc815\ud55c\ub2e4.',
        'The following text 2026-09-27 1It\'s a direct order to the development of the car. 2·3The change in the car. 8.1Tracks the sections and each graph as a cohesive file-sharing, and does not overwrite past instructions with the latest content of the work files.')
    revised = revised.replace('\ud604\ud589 Criteria-Guided Solving\uc5d0\uc11c \uc870\uac74\ubd80 \uc124\uba85\uc740 \ub2e8\uc77c \ub2f5\uc744 \uc720\ubcf4\ud558\uba74\uc11c \uc81c\uacf5\ud560 \uc218 \uc788\ub294 \uc124\uba85 \ubc29\uc2dd\uc774\ub2e4. \ubcc4\ub3c4 \ubd84\ub958 \ub77c\ubca8\uc744 \ucd9c\ub825\ud558\ub294 \ud544\ub4dc\ub294 \uc5c6\uc73c\uba70, \uad6c\ubd84\uc740 `answer`\uc640 `explanation`\uc758 \ub0b4\uc6a9\uc5d0 \ub098\ud0c0\ub09c\ub2e4. \uc870\uac74\ubd80 \uc124\uba85\uc758 \uae30\uc900\uc5d0 \ud574\ub2f9\ud558\uba74 \uc720\ubcf4 \uc774\uc720\uc640 \ud568\uaed8 \uc870\uac74\ubcc4 \uacb0\uacfc\ub97c \uc81c\uc2dc\ud55c\ub2e4.',
        'The input classification is ANSWERABLE / CONFLICT / INSUFFICIENT_EVIDENCE / UNRESOLVED and the response method is ANSWERE / CONDITIONAL / ABSTAIN. `explanation` `Classification: <CLASS>; Response: <MODE>.`Thus, it does not estimate the classification by null or by itself, but verifies together with the actual declaration and the reason. Unguided Solving does not include this classification instruction.')
    revised = revised.replace('P0\uc5d0\ub294 \uc774 \ubd84\ub958 \uc9c0\uc2dc\ub97c \ub123\uc9c0 \uc54a\ub294\ub2e4.', 'Unguided Solving does not include this sorting instruction.')
    first = runs()[0][1]
    start, end = '### A.3 Criteria-Guided Solving Conditions Direction Principle', '### A.4 The principle of instruction that applies to both conditions in common'
    if start in revised and end in revised:
        before, rest = revised.split(start, 1)
        _, after = rest.split(end, 1)
        links = ' · '.join(f"[{number}The instructions for classification of the car{root.name}/00-definition/p1-abstention-aware.md)" for number, root, _ in runs())
        revised = before + start + '\n\nThe input classification criteria and the response methodology 1It\'s the driving manual.\n\n' + links + '\n\n```text\n' + (first / '00-definition/p1-abstention-aware.md').read_text().rstrip() + '\n```\n\n' + end + after
    common_start, common_end = '### A.4 The principle of instruction that applies to both conditions in common', '### A.5 Common response structure'
    if common_start in revised and common_end in revised:
        before, rest = revised.split(common_start, 1)
        _, after = rest.split(common_end, 1)
        revised = before + common_start + '\n\nThe field description sequence of the common instruction is separated from the key sequence of response schema, and the precision is the key sequences of public input. `answer_format.decimal_places`It\'s in the following. 1It\'s a common command to the car.\n\n```text\n' + (first / '00-definition/common.md').read_text().rstrip() + '\n```\n\n' + common_end + after
    if revised != text:
        old_hash = store.file_hash(paper)
        store.write_text(paper, revised)
        store.event(REPORT, 'PAPER_UPDATED', source=str(paper.relative_to(store.PROJECT)), before_sha256=old_hash, after_sha256=store.file_hash(paper), completed_analysis_rounds=len(rows))
    source_file = paper.parent / 'sources.json'
    sources = store.read(source_file, {})
    evidence_files = [{'path': str(p.relative_to(store.PROJECT)), 'sha256': store.file_hash(p)}
        for _, root, _ in runs() for p in [root / 'manifest.json', root / 'summary.json',
            root / '02_analysis/02_comparison/summary.json', root / '02_analysis/02_comparison/rows.jsonl', root / 'events.jsonl'] if p.exists()]
    if sources.get('development_study', {}).get('files') != evidence_files:
        sources['development_study'] = {'campaign': CAMPAIGN, 'updated_at': store.now(), 'status': 'EXPLORATORY_NOT_CONFIRMATORY',
            'files': evidence_files}
        store.write(source_file, sources)
    return True


def tick():
    """Advance completed stages; stop at the scientific-review decision boundary."""
    if any(event.get('event') == 'USER_REVIEW_RESET' for event in store.rows(REPORT / 'events.jsonl')):
        return {'status': 'CODEX_REVIEW_AND_USER_DISCUSSION_REQUIRED', 'api_calls': 0,
                'next': 'Review round-one solver outputs in this Codex conversation. Agree improvements with the user before another experiment.'}
    cohort = runs()
    if not cohort:
        raise ValueError('FIRST_ROUND_NOT_PREPARED')
    number, root, config = cohort[-1]
    first = cohort[0][1]
    pipeline.run(root)
    state = store.read(root / 'state.json')
    if state['status'] != 'FINISHED':
        write_report()
        return {'round': number, 'run': root.name, 'status': state['status']}
    stage = semantic.run_stage(first, semantic.prepare_input(first))
    if stage['status'] != 'COLLECTED':
        write_report()
        return {'round': number, 'status': 'INPUT_REVIEW_PENDING', 'stage': stage}
    recovery = semantic.recover_stage(first, first / semantic.ROOT / '01-LLM-input')
    if recovery['status'] != 'COLLECTED':
        write_report()
        return {'round': number, 'status': 'INPUT_REVIEW_RECOVERY_PENDING', 'stage': recovery}
    for audit in (False, True):
        folder = semantic.prepare_response(root, first, audit=audit)
        stage = semantic.run_stage(root, folder)
        if stage['status'] != 'COLLECTED':
            write_report()
            return {'round': number, 'status': 'AUDIT_PENDING' if audit else 'RESPONSE_REVIEW_PENDING', 'stage': stage}
        recovery = semantic.recover_stage(root, folder)
        if recovery['status'] != 'COLLECTED':
            write_report()
            return {'round': number, 'status': 'REVIEW_RECOVERY_PENDING', 'stage': recovery}
    semantic.build(root, first)
    update_paper()
    write_report()
    return {'round': number, 'run': root.name, 'status': 'CRITICAL_REVIEW_REQUIRED',
            'next': 'Read judgments, audit disagreements and counterexamples. Record specific evidence and changes before preparing the next round.'}


def prepare_next(config_path):
    """Enforce review and paper completion before another 3,000 solver calls."""
    cohort = runs()
    number, previous, _ = cohort[-1]
    if number >= 3:
        raise ValueError('AUTHORIZED_THREE_ROUNDS_ALREADY_PREPARED')
    config = store.read(config_path)['experiments']
    improvement = config.get('improvement', {})
    if improvement.get('campaign') != CAMPAIGN or improvement.get('round') != number + 1 or improvement.get('previous_run') != previous.name:
        raise ValueError('NEXT_ROUND_IDENTITY_MISMATCH')
    if not (previous / '02_analysis/02_comparison/summary.json').exists():
        raise ValueError('PREVIOUS_ANALYSIS_REQUIRED')
    reviews = [e for e in store.rows(previous / 'events.jsonl') if e.get('event') == 'STUDY_CRITICAL_REVIEW']
    if not reviews or not reviews[-1].get('report_ko') or not reviews[-1].get('paper_ko'):
        raise ValueError('PREVIOUS_CRITICAL_REVIEW_REQUIRED')
    if not update_paper():
        raise ValueError('PREVIOUS_PAPER_UPDATE_REQUIRED')
    first = cohort[0][1]
    if (store.PROJECT / config['dataset'].get('reuse_input_run', '')).resolve() != first:
        raise ValueError('FIRST_COHORT_REUSE_REQUIRED')
    if config.get('definition_source_run'):
        raise ValueError('NEXT_ROUND_MUST_FREEZE_REVIEWED_WORKING_PROMPTS')
    frozen = pipeline.run_layout.definition(first)
    controls = [(assets.prompt_path('solver_common'), frozen / 'common.md'),
                (assets.prompt_path('solver_unguided'), pipeline.run_layout.prompt_file(frozen, 'P0'))]
    for current, previous_control in controls:
        if store.file_hash(current) != store.file_hash(previous_control):
            raise ValueError('UNCHANGED_CONTROL_PROMPT_REQUIRED:' + current.name)
    new = pipeline.prepare(config_path)
    for name in ('public.jsonl', 'private.jsonl'):
        if store.file_hash(new / '01-input' / name) != store.file_hash(first / '01-input' / name):
            raise ValueError('COHORT_BYTES_CHANGED:' + name)
    store.event(new, 'PREVIOUS_ROUND_REVIEW_APPLIED', previous_run=previous.name, previous_review_time=reviews[-1]['time'],
        unchanged_controls=[current.name for current, _ in controls], paired_cohort_source=first.name)
    write_report()
    return new


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['tick', 'report', 'paper', 'prepare-next'])
    parser.add_argument('--config', default=str(store.PROJECT / 'config/experiments-luna-improvement.json'))
    args = parser.parse_args()
    if args.action == 'prepare-next':
        with store.locked(REPORT / '.study.lock'):
            print(prepare_next(args.config))
    elif args.action == 'tick':
        REPORT.mkdir(parents=True, exist_ok=True)
        with store.locked(REPORT / '.study.lock'):
            try:
                print(json.dumps(tick()))
            except Exception as error:
                store.event(REPORT, 'STUDY_ADVANCE_FAILED', error_type=type(error).__name__, error=str(error))
                write_report()
                raise
    elif args.action == 'paper':
        print(json.dumps({'paper_updated': update_paper()}))
    else:
        write_report()
        print(REPORT / 'README.md')
