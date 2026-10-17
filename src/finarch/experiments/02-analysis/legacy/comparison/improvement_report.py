"""Render the saved improvement evidence in the existing documentation viewer."""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit

from finarch.paths import PROJECT as ROOT
OUT = ROOT / 'reports/run/20260923-experiment-improvement'
TEMPLATES = Path(__file__).parent


def read(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def validate_document_index(documents):
    """Check the just-built viewer index without changing experiment evidence."""
    errors, checked_links = [], 0
    for row in documents:
        path = ROOT / row['path']
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            errors.append('INDEX_FILE_OR_HASH:' + row['path'])
            continue
        if path.suffix != '.md':
            continue
        for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)', path.read_text()):
            parsed = urlsplit(target)
            if parsed.scheme or target.startswith(('#', 'mailto:')):
                continue
            checked_links += 1
            if not (path.parent / unquote(parsed.path)).exists():
                errors.append('BROKEN_LINK:' + row['path'] + ':' + target)
    result = {'status': 'PASS' if not errors else 'FAIL',
              'checked_at': datetime.now(timezone.utc).isoformat(),
              'current_documents': len(documents), 'checked_local_links': checked_links,
              'errors': errors, 'model_calls': 0,
              'scope': 'Current improvement-run document index, hashes and local links only; no semantic evaluation.'}
    write(OUT/'current-documentation-validation.json', result)
    if errors:
        raise ValueError('CURRENT_DOCUMENTATION_VALIDATION_FAILED')


def template(name, target, values=None):
    body = (TEMPLATES / name).read_text()
    for key, value in (values or {}).items():
        body = body.replace('{{' + key + '}}', str(value))
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(body)


def run_analysis_files(run_id):
    """Include only analysis artifacts that exist for the currently selected run."""
    folder = OUT/'03-research'/run_id
    candidates = [
        ('findings.md', 'Improvements in the key results of the re-experiment'),
        ('bounded-output.md', 'Limit the output length 120Check the trail.'),
        ('bounded-output.json', 'Limiting the length 60Dual: raw response: verification of presence'),
        ('README.md', 'The re-experimental analysis guide'),
        ('analysis.md', 'Re-experimental results analysis'),
        ('cases.md', 'Re-experimentation is a real case.'),
        ('comparison.json', 'Conventional and new response comparison data'),
        ('intent-case-comparison.json', 'Diagnostic cases 20Pair and raw response basis'),
        ('summary.json', 'The re-experimental analysis of the'),
        ('comparator-summary.json', 'Comparison of the statistics'),
        ('contrasts/analysis.md', 'The analysis of the corresponding pairs by condition'),
        ('pilot/README.md', 'Diagnosis 300The Conditions Analysis Guide'),
        ('pilot/analysis.md', 'Diagnosis 300Conditions of observation'),
        ('pilot/decision.json', 'Expanded judgement after diagnosis'),
    ]
    files = [(folder/name, title) for name, title in candidates if (folder/name).is_file()]
    status = read(OUT/'status.json', {})
    first_run = status.get('first_refined_run')
    if first_run and first_run != run_id and Path(first_run).name == first_run:
        first = OUT/'03-research'/first_run
        for name, title in [('findings.md', 'The first collection of repeat criteria.'),
                            ('analysis.md', 'First collection of the full analysis'),
                            ('intent-case-comparison.json', 'First collected diagnosis 20Changes in conditions')]:
            if (first/name).is_file():
                files.append((first/name, title))
    repeat_path = status.get('repeat_analysis_output')
    if repeat_path:
        repeat = (ROOT/repeat_path).resolve()
        if (OUT/'03-research').resolve() not in repeat.parents:
            raise ValueError('REPEAT_ANALYSIS_MUST_BE_INSIDE_RESEARCH_REPORTS')
        for name, title in [('README.md', 'The same condition repeat analysis guide'),
                            ('analysis.md', 'The same condition repeated results'),
                            ('summary.json', 'Repeated matching: change set')]:
            if (repeat/name).is_file():
                files.append((repeat/name, title))
    for bounded_run in status.get('bounded_followup_runs', []):
        if Path(bounded_run).name != bounded_run:
            raise ValueError('BOUNDED_RUN_MUST_BE_A_RUN_NAME')
        bounded = OUT/'03-research'/bounded_run
        for name in ('README.md', 'analysis.md'):
            if (bounded/name).is_file():
                files.append((bounded/name, f'{bounded_run} Small verification {name}'))
    ledger = OUT/'03-research/continuation-cost-ledger.json'
    if ledger.is_file():
        files.append((ledger, 'The actual call-in and cost estimate of this work'))
    return files


def run_analysis_section(status, files):
    if not files:
        return ''
    phase = status.get('phase', 'IN_PROGRESS')
    progress = ('The following is a real stored analytical file, and the basis for determining whether the analysis is complete and whether the judgement is based on each file.'
                if phase == 'COLLECTION_COMPLETED' else
                'Below is the current analytics file, which may have been created in the middle of the collection, so it doesn\'t mean that it\'s just being there.')
    links = ' · '.join(f'[{title}]({path.relative_to(OUT).as_posix()})' for path, title in files)
    repetition = ('The results of two observations of the same condition are confirmed by a linked iterative analysis, and the two coincidences do not confirm long-term reliability or meaningful answers.'
                  if status.get('repeat_analysis_status') == 'COMPLETED' else
                  'The stability of the same condition repeating is still underestimated.')
    return (f"\n\n## The current run is analyzed {status['improved_run_id']}\n\n"
            f"Storage status **{phase}**. {progress}\n\n{links}\n\n"
            'The existing format and the modified format differ from the response structure and analysis rules. The format does not interpret the increase in valid responses as a purely problem-solving ability improvement. '
            'No number, null, and whether or not it\'s a proper ubo. ' + repetition)


def build():
    status = read(OUT/'status.json',{})
    run_id = status['improved_run_id']
    run = ROOT/'reports/experiments-run'/run_id
    summary = read(run/'summary.json',{})
    active_experiment = status.get('active_scope') == 'IMPROVED_LUNA_REEXPERIMENT'
    summary_calls = sum(m.get('attempts',0) for m in summary.get('models',[]))
    calls = status.get('experiment_request_attempts', summary_calls) if active_experiment else summary_calls
    # Provider responses and format-valid responses are different observations.
    successful = status.get('successful_responses', 'Unconfirmed')
    current_review = status.get('current_review') if active_experiment else 'EXISTING_RESPONSE_INTENT_REVIEW'
    title = 'Luna improvements and re-experimental situation and existing analysis' if active_experiment else 'Problems and improvements to the existing Luna response review'
    run_status = (f"{'Current repeat experiment' if active_experiment else 'Earlier rerun history'}: **{run_id}** · "
                  f"Try this run API request **{calls}** · New provider responses: **{successful}entries** · "
                  f"Save the run **{status.get('phase','IN_PROGRESS')}**. "
                  'Confirming a response does not mean passing a form or meaningful response.')
    current_intro = (
        '**The current task is to retry the user-directed improvements.** ' + run_status + '\n\n'
        f"[Fixed request for current run, status, output record]{run_id}First, look at the /README.md. "
        'The existing raw response diagnoses below are preserved as analyses completed before retesting. Improvement effects, accuracy of purpose, and reverse stability are the subjects of separate evaluation, and the reporting itself does not call for a model.'
        if active_experiment else
        '**Now, the task is to review the existing raw response in the original test setting, and first sort out the problems and improvements that we\'ve identified.** It distinguishes between the fact that the data is stored and the judgement that the actual response of the model has improved. 0calls.')
    analysis_files = run_analysis_files(run_id)
    current_intro += run_analysis_section(status, analysis_files)
    repeat_complete = status.get('repeat_analysis_status') == 'COMPLETED'
    if repeat_complete:
        repeat_summary = read(ROOT/status['repeat_analysis_output']/'summary.json', {})
        observed = repeat_summary.get('overall', {})
        current_intro += (
            '\n\n## This continues to be the number of completion of the work\n\n'
            f"The real call **{status.get('continuation_actual_calls', 0):,}times**: "
            'Diagnosis at the front. 300 + improvement total 3,000 + the same condition repeat 3,000 + length limit verification 120. '
            'The missile operation of each run was preserved, and a small check was made of the entire 100It\'s not a re-examination of the original.\n\n'
            f"And the answer is observed on both sides of the repeat. **{observed.get('answer_observed_pairs', 0):,}Couple of them.** of "
            f"The same pair as the number-unit or null is **{observed.get('same_answer_and_scale', 0):,}items**. "
            f"The number-null conversion is **{observed.get('numeric_to_null', 0)+observed.get('null_to_numeric', 0):,}items**. "
            'We\'ve distinguished between form-use complementarity and the stability of the baseline selection judgement, and we\'ve sorted out the key results. '
            'The follow-up length limit verification is 120All the rounds are form-pass. 0But it\'s not a complete proof of meaning stability.\n\n'
            f"The cost estimate for this continuing work is the **${status.get('continuation_paid_api_usage_cost_estimate_usd', 0):.7f}**And it\x27s not the bill value.")
    intent = read(OUT/'03-research/intent-review-evidence.json',{})
    review_cases = intent.get('selected_case_count','Unconfirmed')
    review_responses = intent.get('selected_response_count','Unconfirmed')
    review_files = len(intent['source_sha256']) if isinstance(intent.get('source_sha256'),dict) else 'Unconfirmed'
    status.update(improved_run_id=run_id, model_calls=calls, experiment_request_attempts=calls,
                  report_new_model_calls=0,
                  updated_at=datetime.now(timezone.utc).isoformat())
    if not active_experiment:
        status['current_review'] = current_review
    write(OUT/'status.json',status)
    template('improvement-report-template.md',OUT/'README.md',{
        'status':status.get('phase','IN_PROGRESS'),'run_id':run_id,'calls':calls,
        'successful':successful,'review_cases':review_cases,'review_responses':review_responses,
        'review_files':review_files,'title':title,'current_intro':current_intro,
        'run_status':run_status,'run_link_label':'The current re-test data' if active_experiment else 'The data for the future'})
    template('a100-review-template.md',OUT/'02-a100/README.md')
    template('research-review-template.md',OUT/'03-research/README.md')
    remote=read(OUT/'02-a100/source/summary.json',{})
    a=['# A100 The scope of the data','',f"Distance estimate view: `{remote.get('updated_at')}` · Storage status `{remote.get('status')}`. It\x27s a read-only collection and not a result of verifying the current survival of the remote process.",'',
       'The model is a plan, a plan, and a plan.','|---|---:|---:|---:|---:|---|']
    for m in remote.get('models',[]):
        a.append(f"|{m['key']}|{m['planned']:,}|{m['recorded']:,}|{m.get('schema_valid','Not evaluated')}|{m.get('truncated','Not evaluated')}|{m['status']}|")
    a += ['', '## What\'s in this improvement?', '',
      '- **Adopted:** It keeps the whole plan, the actual attempt, the summit finish, the format pass, the cut, the misspellings apart. 100%It doesn\'t change.',
      '- **Adopted amendments:** So if the output of the inference is longer, then we see the velocity, the magnitude, the decay.8B Cut from the record. 211That\'s the preemption sample sum. 1,417And KV peak. 1.0This looks like it\'s together, but this statistic alone doesn\'t confirm what\'s causing it.',
      '- **The reservation:** Compare the capabilities of the financial model to those of the direct-based model. In this collection, there\'s not a single instance of financial model that\'s not EXECUTABLE.',
      '- **- What is it?** Remotely. 1,080The items-eating group and Luna. 100So we\'re going to have to compare the aggregate of the cluster of source items to the model hierarchy, and then we\'re gonna have to first match the cohort groupings, the Q/C contracts, the formulations, the sampling, the revision, the quantization conditions.',
      '', 'Luna none/medium and Qwen native toggles for each are not the same measurement of inference. They don\'t change the output of the response to match the processing amount. So they didn\'t bring in the raw of the remote, so the basis for meaningful correspondence improvement for P0/P1 is only reviewed in this Luna raw response.', '']
    (OUT/'02-a100/analysis.md').write_text('\n'.join(a))
    base=read(OUT/'01-baseline/summary.json',{}); overall=base.get('overall',{}); tags=overall.get('tags',{})
    plan=read(run/'plan.json',{}); model=(plan.get('models') or [{}])[0]
    quota=read(OUT/'quota-preflight.json',{})
    authorization=read(OUT/'execution-authorization.json',{})
    user_managed_usage=authorization.get('scope',{}).get('account_usage_monitoring')=='USER_MANAGED'
    quota_note=('In the execution authorization, the user is set to directly manage account usage.35And the call attempt, cost, cache recording conditions remain in execution-authorization.json. The report creation itself does not monitor account usage or call the model.' if user_managed_usage else f"The previously stored limit check transition `{quota.get('status','NOT_CHECKED')}` / `{quota.get('reason','')}`. The report itself does not create new boundary observations or model calls.")
    lines=['# '+title+' The report.','',
      current_intro,'',
      '[Problems and improvements](../../../docs/02-experiments/02_analysis/02_comparison/README.md) → [Reviewed raw response and evidence](03-research/intent-review-evidence.json) → Read in the following order of observation and suggestion.', '',
      f"{'Completed before the retest.' if active_experiment else 'This time.'} The intent response review is the original **{review_cases}items**, selected response **{review_responses}items**The base file. **{review_files}items**The map is linked to a diagnostic case that was chosen for the purpose and is not a random sampling of the overall error rate or a new meaningful response.", '',
      f"The file name of the current response format `FinancialAnswerMagnitudeV4`(Exp.006The code used in the file name. `FinancialAnswerV6`New response returned by the provider {successful}The number of identifier names does not refer to the model version or the sixth experiment. Below, we call it the existing format-conversioned format.", '',
      '## Users\' intent and document structure','',
      'The purpose of the experiment is to basically unlock the question-text provided in P0 and guide you to consider the source conditions of the basis for the sufficiency, the conflict, and the question-question in P1. But the existing common guidelines also contain a law of e-mail and a conditional answer, and the existing P0 should not be interpreted as a condition in which there is no action at all. The modified form judgment guidelines are not intended to be collected into P1.','',
      'Providing the same common JSON structure for both conditions is a measure of matching the expression conditions, and the impact that the structure has on model behavior is a measure that is used to measure the impact of the structure on model behavior. 0The goal is to distinguish between the accuracy of the answer and the compliance of the form, the consistency of the response and the explanation, and the sensitivity to change in conditions. ' + ('Two real observations of the same condition follow repeated analysis and distinguish between general confidence and objective truth.' if repeat_complete else 'The repeatability of the same conditions is not underestimated.'),'',
      '[Experimental document](../../../docs/02-experiments/README.md)is the whole00_input→01_evaluation→02_analysis ordered the expected results at each stage, linking the required actions, actual files, fractions, failures, evaluations, results, and Mermaid, preserving the existing docs archives and the raw response of the existing formats.','',
      '## completed the existing data review and the actual Luna results confirmed the issue','',
      f"Raw response {overall.get('planned')}They were all read in JSON and passed the type of the schematics at the time, but the additional rules are that they\x27re all written in JSON. {overall.get('saved_status',{}).get('VALID',0):,}entries passed, and {overall.get('saved_status',{}).get('INVALID_RESPONSE',0):,}The UBO declaration and the numeric/numeric code simultaneously. {tags.get('DECLARED_ABSTENTION_WITH_NON_NULL_ANSWER')}That\x27s a failure of the digits. {tags.get('SAVED_DECIMAL_PLACES_FAILURE')}So just by increasing the simple JSON pasting rate, you can\x27t guarantee that the expression is right for the user\x27s intent.",'',
      f"If you read the entire response again, the inconsistent quotation string. {tags.get('EVIDENCE_NOT_EXACT_SUBSTRING')}/3,000The exact matching of strings itself is not a guarantee that it\x27s a meaningful supporting basis. 16originals ·32It\x27s a items request and the existing input hasn\x27t been modified.",'',
      'The number of digits is zero, and the number of digitals is zero.','|---|---:|---:|---:|---:|---:|']
    for m in base.get('by_original_reasoning',[]):
        x=m['original_outcomes'];lines.append(f"|{m['reasoning']}|{m['planned']}|{x.get('NUMERIC_MATCH',0)}|{x.get('NUMERIC_MISMATCH',0)}|{x.get('FORMAT_OR_COLLECTION_FAILURE',0)}|{x.get('VALID_NULL_ANSWER',0)}|")
    lines += ['', '[Detailed denominator, model, example, source hash](01-baseline/README.md)So we don\'t call the off/on uniformity repeated stability because it\'s not a data that repeats the same condition.', '',
      '## Re-experiment before the change in implementation range','',
      'Below is the content that is implemented in the file and local checks, describing the implementation status of the previously saved changes, and not showing the implementation as completed until the newly proposed ones are reviewed in this case.', '',
      'The content of the file is implemented in a way that limits the problem and the interpretation.','|---|---|---|',
      'The common JSON number is null, description, usage, metadata, status, and status, and the statements and the contradictions of the numbers. 211The building cannot be observed in the same way after the status is deleted.',
      'P0/P1 - Explanation of the public schematic: one-way word restrictions, sufficient to P1, conflict, source of information, guidance on the use of language tests, not showing meaningful neutrality.',
      'Explain the matching of the numeric and the syllable, null, and metadata, both null, output, and precision, and you\'re not going to fix the raw response or change the correct answer to the value.',
      'The function of the statements, the meaning of the statement, the approximation of the statistic, the existence of the statistical character, the existence and the observation of the statistics, the observation value, the observed value, the statisical value, the observational value, the value of the statism, the statistic value, the data, the statistics and the statistics of the statistical statistics, and the statistics of the statists, the statements and the statements of the statutes, the statutes and the statutes of the statuses, the statuses and statements of statements, and the data, and the results of the states and statements, are not verified.',
      'The output accuracy of the Q/C metadata is conserved, the metadata in collision is specified, the precision of the location and the precision is determined. 16You have to distinguish the input principle.',
      'The actual management of the system is the copy, request, and storage of the data, maximum per turn. 100The callback, recall, transmission, unnamed, usage volume shortfall, blocked, fuel budget is token-based estimates and the amount of the claim is either a security or a security.',
      '', '## to review the proposed improvements to the scope yet to be confirmed', '',
      '[Problems and improvements](../../../docs/02-experiments/02_analysis/02_comparison/README.md)We gathered the suggestions and judgments, and we identified the boundaries of the common expression clause and the P1 judgments guidelines, and we first identified the minimum information needed to connect the final number, the conditional part value, the source condition, and the circle in the real case.', '',
      'Conditional result fields, base ID values, and overlay adjective metadata reductions are subsequent design candidates. New fields can change even the behavior of P0, so they don\'t confirm neutrality or improvement by introduction alone. If you introduce P0/P1, you have to fix the common input/schema check and compare the effect of the change separately.', '',
      '## Conversations that link existing observations to papers','',
      '1. **Separation of response expression and judgment:** So, as you can see, we keep the numbers filled in at the raw response level, and then we check them again after the improvement agreement, based on common observations.',
      '2. **The difference of guidance × inference × transformation:** It connects the null transitions within P1 to how they differ from off/on and VALUE/SOURCE/RELATION/EA on a peripheral basis.',
      '3. **After the source is installed:** So we compare the SOURCE to the actual parent VALUE, and we don\'t call the mixed comparison of the front/back position with the other parent as a single-source effect.',
      ('4. **Repeat the same condition:** The same actual transfer bytes 3,000We collected the conditions twice and recorded the numerical input, value, level, form and functional variables in repeated analysis. The P1 standard counterpart did not run, so the appropriate rate of inflation or the degree of excess inflation is underestimated.' if repeat_complete else '4. **Stability of the same conditions:** It\'s still a measurement. Independent repetition of a fixed request and the primitive P1 counterpart are the subsequent verification candidates.'),
      '5. **External model:** A100 The data is current, time-efficient, and there is no response to the financial model test, and the financial tuning effects comparison is in place.', '',
      '[calculated response rates and study judgments](03-research/analysis.md) · [Real case of intent response](03-research/qualitative-cases.md) · [A100 Observation](02-a100/analysis.md)This one. 100The original is a group used in the improvement process, and the final verification of the paper should be separated from the group that hasn\'t been developed by a set of criteria.', '',
      '## Completed local verification and remaining judgement','',
      'The local mobility of the existing change response format, API, limit execution of the return check record is 04This is different from verifying that the actual model followed the instructions. 12,008I\'ve verified the hash preservation of the items file. The selection case and the base file of this intent response review have been linked separately to intent-review-evidence.json. The document link;README generated; the actual browser verification follows a separate record and is not displayed as a user review completed.', '',
      ('The current retest is a follow-up to the previous diagnosis. ' if active_experiment else 'The priority now is to review the problems identified in the existing responses and the minimum improvements. ') + ('We\'ve completed two complete collections and a small verification of length limits: the observed improvements and repeated fluctuations follow the key results, meaning accuracy, long-term reliability, and generalization outside the development group is underestimated.' if repeat_complete else 'The model effect of the change of form, the precision of meaning, the repeatability of the same conditions are the remaining judgments.'), '',
      '## Current record of the retest' if active_experiment else '## forward re-enactment attempts lead to the current raw response review and separation', '',
      run_status + ' This is not the number of new calls in the report creation.', '',
      f"The plan at the time was to model `gpt-5.6-luna`Same as the original. 100· variants 700, total {model.get('requests',3000):,}It was a request. none/medium, cache ban, simultaneous. 50items, the power is out. 8,192I\x27ve prepared it with tokens. {model.get('input_token_estimate',0):,}Tokens, output 1,000$$$$${model.get('api_equivalent_estimate_usd_at_1000_output_tokens',0):.4f}The total use of the household is about $1,500.30.35Set the budget to run.35The price is recorded as the official document of OpenAI Luna.](https://developers.openai.com/api/docs/models/gpt-5.6-luna)And that doesn\x27t mean that the report reviewed the latest prices.", '',
      quota_note, '',
      'Regular checks for night reading have a temporary effect after morning reporting. This report creation itself does not restart the automation or run the next model call. ' + (f"The experiment was not fixed run `{run_id}I\x27m going to go through the ` and I\x27m gonna go through the existing case review and I\x27ll go through the execution." if active_experiment else 'If we\'re going to run it again, we need to keep the fixed request and performance settings as separate runs, and we need to distinguish between the current case review and the execution results.'), '']
    blocker = read(OUT/'api-blocker.json', {})
    if blocker.get('run_id') and (active_experiment or (blocker.get('run_id') == run_id and status.get('phase') == 'API_CREDIT_BALANCE_EXHAUSTED')):
        lines += ['', 'External blocking verified by the forward request', '',
            f"Below is the [prevailing api-blocker.json]](api-blocker.json)recorded in `{blocker['run_id']}`\x27s past performance. The current state of execution follows the top of the report.", '',
            'I sent the first request to the OpenAI API, but HTTP 429and `credit_balance_exhausted`The provider\'s message was that there was no API credit balance and that it needed to be charged. 1Round, normal model response 0And the rest of the requests were not sent.', '',
            'This state is not a stop following automatic account usage checks. Usage was applied to user-direct control. The initial classifier saved the record that marked it as RATE_LIMITED, and the exact cause was not recorded in api-blocker.json as QUOTA_EXHAUSTED. It\'s not a speed limit for a simple re-request of the same key.', '',
            'This is the blocking effect of the forward re-run request and does not represent the current status of the new run. The raw response and the existing score have not been corrected, leaving the actual charge as uncertain.', '']
    lines[2:2] = ['[Complex case array](http://127.0.0.1:8895/dashboard/01-overview/) · [Problem analysis dashboard]](http://127.0.0.1:8895/dashboard/02-explorer/)It connects the actual numbers, the score, the score and the response.', '']
    content_analysis = OUT/'03-research/20260924-content-analysis'
    if (content_analysis/'analysis.md').is_file():
        lines[2:2] = ['[R0/R1 source; variable condition analysis](03-research/20260924-content-analysis/analysis.md): Form: Separate the numerical matching and the content sub-matching.', '']
    (OUT/'REPORT.md').write_text('\n'.join(lines))
    docpaths=[OUT/'README.md',OUT/'REPORT.md']
    docs_root = ROOT/'docs/02-experiments'
    overview = [docs_root/'README.md']
    docpaths += overview + sorted((p for p in docs_root.rglob('*.md') if p not in overview),
                                  key=lambda path: str(path).replace('/README.md', '/'))
    docpaths += [OUT/'01-baseline/README.md',OUT/'01-baseline/analysis.md',OUT/'01-baseline/cases.md',
                 OUT/'02-a100/README.md',OUT/'02-a100/analysis.md',
                 OUT/'03-research/README.md',OUT/'03-research/analysis.md',OUT/'03-research/qualitative-cases.md',
                 OUT/'04-validation/README.md']
    analysis_titles = dict(analysis_files)
    docpaths += [path for path, _ in analysis_files if path.suffix == '.md']
    docpaths += [content_analysis/name for name in ('README.md', 'analysis.md', 'summary.json', 'source-hashes.json', 'validation.json')
                 if (content_analysis/name).is_file()]
    documents=[]
    for path in docpaths:
        if not path.exists(): continue
        text=path.read_text(); relative=str(path.relative_to(ROOT))
        documents.append({'path':relative,'title':text.splitlines()[0].lstrip('# ') if text.splitlines() else analysis_titles.get(path, path.name),
            'group':('Re-experimental analysis '+run_id if path in analysis_titles else
                     '02-experiments' if relative.startswith('docs/') else path.parent.name),
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    navigation=[['Problems and improvements','docs/02-experiments/02_analysis/02_comparison/README.md'],
                ['Work reports',str((OUT/'REPORT.md').relative_to(ROOT))],['All experiments','docs/02-experiments/README.md'],
                ['The Luna is ready.',str((OUT/'01-baseline/analysis.md').relative_to(ROOT))],
                ['The essay',str((OUT/'03-research/analysis.md').relative_to(ROOT))],
                ['A100',str((OUT/'02-a100/analysis.md').relative_to(ROOT))]]
    navigation[0:0] = [[title, str(path.relative_to(ROOT))]
                       for path, title in analysis_files if path.suffix == '.md']
    if (content_analysis/'analysis.md').is_file():
        navigation.insert(0, ['R0/R1: variable analysis', str((content_analysis/'analysis.md').relative_to(ROOT))])
    evidence_path=OUT/'03-research/intent-review-evidence.json'
    evidence_files=([{'path':str(evidence_path.relative_to(ROOT)),
                     'title':'The existing raw response intent response review basis',
                     'sha256':hashlib.sha256(evidence_path.read_bytes()).hexdigest()}]
                    if evidence_path.exists() else [])
    evidence_files.extend({'path':str(path.relative_to(ROOT)), 'title':title,
                           'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
                          for path, title in analysis_files if path.suffix == '.json')
    documents.extend({**item, 'group':'03-research'} for item in evidence_files)
    write(OUT/'documentation.json',{'kind':'PIPELINE_DOCUMENTATION','title':title,
        'documents':documents,'navigation':navigation,'entry_document':str((OUT/'REPORT.md').relative_to(ROOT)),
        'evidence_files':evidence_files,
        'model_calls':0,'new_model_calls':0,'experiment_request_attempts':calls,
        'scope':('Improved Luna reexperiment; report generation uses no model calls and preserves prior response analysis.' if active_experiment else 'Existing response review and report generation use no model calls; earlier experiment attempts are recorded separately.')})
    validate_document_index(documents)
    write(OUT/'migration.json',[])
    write(OUT/'summary.json',{'kind':'PIPELINE_DOCUMENTATION','documents':len(documents),
        'status':status.get('phase'),'current_review':current_review,'active_scope':status.get('active_scope'),
        'model_calls':0,'new_model_calls':0,'experiment_request_attempts':calls})
    with (OUT/'events.jsonl').open('a') as f:
        f.write(json.dumps({'at':status['updated_at'],'event':'REPORT_REFRESHED','documents':len(documents),
                            'new_model_calls':0,'model_calls':0,'experiment_request_attempts':calls})+'\n')
    print(json.dumps({'run_id':run_id,'documents':len(documents),'new_model_calls':0,
                      'experiment_request_attempts':calls}))


if __name__ == '__main__':
    build()
