"""Reproducible post-run diagnostics from preserved responses; no model calls."""
import argparse
import json
import re
from collections import Counter
from pathlib import Path, PurePosixPath

read = __import__('finarch.experiments.90-operations.storage', fromlist=['read']).read
rows = __import__('finarch.experiments.90-operations.storage', fromlist=['rows']).rows
write = __import__('finarch.experiments.90-operations.storage', fromlist=['write']).write
write_rows = __import__('finarch.experiments.90-operations.storage', fromlist=['write_rows']).write_rows
write_text = __import__('finarch.experiments.90-operations.storage', fromlist=['write_text']).write_text
event = __import__('finarch.experiments.90-operations.storage', fromlist=['event']).event
now = __import__('finarch.experiments.90-operations.storage', fromlist=['now']).now
VARIANT_NAMES = __import__('finarch.experiments.01-evaluation.04-validation.reporting', fromlist=['VARIANT_NAMES']).VARIANT_NAMES
VARIANT_ORDER = __import__('finarch.experiments.01-evaluation.04-validation.reporting', fromlist=['VARIANT_ORDER']).VARIANT_ORDER

MARKER = re.compile(r'cannot (?:be |reliably |uniquely )?(?:determine|calculate|answer)|insufficient|not enough|underdetermined|unable to|cannot provide', re.I)


def cell(value):
    return str(value).replace('|', '\\|').replace('\n', ' ')


def table(headers, data):
    return ['|' + '|'.join(headers) + '|', '|' + '|'.join('---' for _ in headers) + '|'] + [
        '|' + '|'.join(cell(v) for v in row) + '|' for row in data] + ['']


def main(root):
    root = Path(root).resolve()
    summary = read(root / 'summary.json')
    if summary['status'] != 'FINISHED':
        raise ValueError('COLLECTION_NOT_FINISHED')
    public = {x['item_id']: x for x in rows(root / '01-input/public.jsonl')}
    private = {x['item_id']: x for x in rows(root / '01-input/private.jsonl')}
    output = root / 'analysis'
    output.mkdir(exist_ok=True)
    models, diagnostics = {}, []
    for model in summary['models']:
        name = model['model']
        entries = rows(root / name / '03-results/results.jsonl')
        assert len(entries) == 3000 and len({x['trial_id'] for x in entries}) == 3000
        models[name] = entries
        failure_lines = [f'# {name} Failed response record', '',
            'It\'s a copy of the original question, context, half-response, and check file, and the form error is not a misjudgment.', '']
        for row in entries:
            result = read(root / row['result_path'])
            response = result.get('response')
            answer = response.get('answer') if isinstance(response, dict) else None
            tags = set()
            if row['status'] == 'OUTPUT_TRUNCATED':
                tags.add('OUTPUT_TRUNCATED')
            if isinstance(response, dict):
                if 'answer' not in response:
                    tags.add('ANSWER_MISSING')
                elif answer is None:
                    tags.add('ANSWER_NULL')
                elif type(answer) in (int, float):
                    tags.add('ANSWER_NUMERIC_NOT_STRING')
                for err in result.get('schema_errors', []):
                    tags.add('SCHEMA_' + str(err['rule']).upper())
            elif row['status'] == 'INVALID_RESPONSE':
                tags.add('JSON_PARSE_OR_TOP_LEVEL_TYPE')
            checks = row.get('checks', {})
            comparison = checks.get('numeric_comparison')
            if row['experiment'] == 1 and row['status'] == 'VALID':
                if comparison:
                    tags.add('NUMERIC_MATCH' if comparison['matches'] else 'NUMERIC_MISMATCH')
                else:
                    tags.add('BASELINE_NOT_NUMERICALLY_EVALUATED')
                    if len(checks.get('numeric_tokens', [])) > 1:
                        tags.add('MULTIPLE_NUMERIC_TOKENS')
            if checks.get('all_quotes_present') is False:
                tags.add('QUOTE_NOT_EXACT_SUBSTRING')
            if row['status'] == 'VALID' and not response.get('evidence'):
                tags.add('EMPTY_EVIDENCE')
            fulltext = json.dumps(response, ensure_ascii=False) if response is not None else ''
            extended = bool(MARKER.search(fulltext))
            diag = {k: row[k] for k in ('trial_id', 'item_id', 'case', 'experiment', 'variant', 'prompt_condition', 'reasoning', 'status', 'result_path')}
            diag.update(model=name, tags=sorted(tags), strict_answer_marker=bool(checks.get('abstention_marker_detected')),
                        response_text_marker=extended, answer_type=type(answer).__name__,
                        numeric_comparison=comparison, schema_errors=result.get('schema_errors', []),
                        finish_reason=result.get('finish_reason'), usage=result.get('usage'),
                        semantic_assessment='NOT_SCORED')
            diagnostics.append(diag)
            if row['status'] != 'VALID':
                rawtext = None
                if response is None:
                    raw = read((root / row['result_path']).parent / 'raw-response.json', {})
                    rawtext = ''.join(p.get('text', '') for c in raw.get('response', {}).get('candidates', [])
                                      for p in c.get('content', {}).get('parts', []) if not p.get('thought'))
                failure_lines += [f"## {row['trial_id']}", '',
                    f"{row['case']} / {row['variant']} / {row['prompt_condition']} / {row['reasoning']} / {row['status']}", '',
                    'Diagnosis: ' + ', '.join(sorted(tags)), '',
                    f"[JSON extract]{row['call_path']}I\x27m not sure what I\x27m saying.{PurePosixPath(row['result_path']).parent}/raw-response.json)", '',
                    '**Questions and Context**', '', '```json', json.dumps(public[row['item_id']], ensure_ascii=False, indent=2), '```', '',
                    '**Returns reply**', '', '```json', json.dumps(response, ensure_ascii=False, indent=2) if response is not None else (rawtext or '(Laughter)'), '```', '',
                    '**The inspector\'s report.**', '', '```json', json.dumps(diag['schema_errors'], ensure_ascii=False, indent=2), '```', '']
        write_text(output / f'{name}-failures.md', '\n'.join(failure_lines))
    write_rows(output / 'response-diagnostics.jsonl', diagnostics)
    ds = {m: [d for d in diagnostics if d['model'] == m] for m in models}
    lines = ['♪ The experiment 1·2 Analysis of responses and failures', '', f"Running: {root.name} · Analysis updates: {now()}", '',
        '**6,000The API request failed. 0The format error. 488Dry and cut off power. 37So that\'s the difference between the right and the wrong.**', '',
        '7All species are PASS candidates. 1,080of, first 100I used items. 100× 2The condition is equal to 200entries, variants 700× 4The condition is equal to 2,800One by one model. 3,000The condition and input are the same between the two models. 6,000We\'ve checked all the items responses, meaning the accuracy of the response rate and the job accuracy is not confirmed in this report.', '',
        '## 1Collecting, forming and spending', '']
    lines += table(['Model','Request','Format valid','Format error','Output truncated','Form-pass rate','Input tokens','Output + reasoning tokens','Estimated USD'],
        [[m['model'],m['planned'],m['statuses'].get('VALID',0),m['statuses'].get('INVALID_RESPONSE',0),m['statuses'].get('OUTPUT_TRUNCATED',0),
          f"{m['statuses'].get('VALID',0)/m['planned']:.2%}",m['input_tokens'],m['output_tokens_including_thinking'],f"{m['paid_batch_usage_cost_estimate_usd']:.6f}"] for m in summary['models']])
    lines += ['The cost is the return usage times the batch unit per model.0.15 / Lite $0.05The output is flash $1.25 / Lite $0.20All requests are paid batch routes, not including the cost of free Claude running in the past.', '',
        '## 2The failure factor classification', '',
        'The tag below can be duplicated, so adding up doesn\'t give you a failure response number. The number of responses, zero, or none, was verified in the actual parsing results. Although the schema was included in the request, the response that violated the format was returned. We can\'t verify why it wasn\'t enforced from within the provider with this data.', '']
    tag_order = ['ANSWER_NUMERIC_NOT_STRING','ANSWER_NULL','ANSWER_MISSING','SCHEMA_TYPE','SCHEMA_REQUIRED','SCHEMA_ADDITIONALPROPERTIES','JSON_PARSE_OR_TOP_LEVEL_TYPE','OUTPUT_TRUNCATED']
    explanations = ['The answer is number: breach of the string agreement.','Answer is null: String contract violation','There\'s no answer field.','Field type violation','Missing required field','Added unallowed fields','JSON pacing or top type problem','Cutting power with MAX_TOKENS']
    lines += table(['Causes',*models], [[desc,*[sum(tag in d['tags'] and d['status']!='VALID' for d in ds[m]) for m in models]] for tag,desc in zip(tag_order,explanations)])
    lines += ['#### I\'m not focused on failure', '']
    lines += table(['Model','Prompt','Inference','Request','Format error','Output truncated','null answer'],
        [[m,p,t,len(z),sum(d['status']=='INVALID_RESPONSE' for d in z),sum(d['status']=='OUTPUT_TRUNCATED' for d in z),sum('ANSWER_NULL' in d['tags'] for d in z)]
         for m in models for p in ['P0','P1'] for t in ['off','on'] if (z:=[d for d in ds[m] if d['prompt_condition']==p and d['reasoning']==t])])
    lines += ['P0 is the experiment. 1 100And then you add that to each of them. 800entries; each P1 condition 700So the denominator should not just compare the number of failures of other rows.', '',
              '## 3The experiment. 1: Number comparison and the printing limit', '',
              'The existing extractor. `-$35` `35`The raw response was unchanged, and the pre-corrected statistics were saved to the analysis/before-currency-sign-fix. Below is the post-correction value.', '']
    lines += table(['Model','Inference','All','Format valid','Numbers are comparable.','Numeric match','Numeric mismatch','It\'s valid, but underrated.'],
        [[m,t,len(z),sum(d['status']=='VALID' for d in z),sum(d['numeric_comparison'] is not None for d in z),sum('NUMERIC_MATCH' in d['tags'] for d in z),sum('NUMERIC_MISMATCH' in d['tags'] for d in z),sum('BASELINE_NOT_NUMERICALLY_EVALUATED' in d['tags'] for d in z)]
         for m in models for t in ['off','on'] if (z:=[d for d in ds[m] if d['experiment']==1 and d['reasoning']==t])])
    lines += ['For example, the answer is zero.2011The sum of years is $86 If you take a millionth of a second, you subtract the numbers of the year and the amount, and you underestimate them, so the fact that the number matches Flash is low doesn\'t make it less soluble than Lite.', '',
              'Both models are the same case where you can compare numbers', '']
    names=list(models)
    pair_data=[]
    for t in ['off','on']:
        maps=[{d['case']:d for d in ds[m] if d['experiment']==1 and d['reasoning']==t and d['numeric_comparison'] is not None} for m in names]
        ids=set(maps[0])&set(maps[1]);counts=Counter((maps[0][i]['numeric_comparison']['matches'],maps[1][i]['numeric_comparison']['matches']) for i in ids)
        pair_data.append([t,len(ids),counts[True,True],counts[True,False],counts[False,True],counts[False,False]])
    lines += table(['Inference','Shared comparison cases','Both numbers match.','Flash only matches.','Just a little match.','They\'re both inconsistent.'],pair_data)
    lines += ['## 4The experiment. 2: The relationship between Ubo expression and form failure', '',
        'The denominator of each row is the same. 100It\'s true. Strict detection only checks the answer fields of the formatting pass response. Extensive detection finds the same regular expression in the entire response string that has been parsed, including the formatting failure. Extensible detection also responds to explanation and user language, so you can\'t use it as a reference accuracy or final reference dry.', '']
    variant_rows=[]
    for v in list(VARIANT_ORDER)[1:]:
        for p in ['P0','P1']:
            for t in ['off','on']:
                values=[VARIANT_NAMES[v],p+'/'+t]
                for m in models:
                    z=[x for x in ds[m] if x['variant']==v and x['prompt_condition']==p and x['reasoning']==t]
                    values += [sum(d['status']=='VALID' for d in z),sum(d['strict_answer_marker'] for d in z),sum(d['response_text_marker'] for d in z),sum('ANSWER_NULL' in d['tags'] for d in z)]
                variant_rows.append(values)
    lines += table(['Type','Condition',*sum(([m+' Valid',m+' Strict detection.',m+' The full alphabet detector.',m+' null'] for m in models),[])],variant_rows)
    lines += ['Changes in the same case when the prompt changes', '',
              'Experiment 2So both P0 and P1 are just cases that have passed through the form.', '']
    pair=[]
    for m in models:
        for t in ['off','on']:
            maps=[{(d['case'],d['variant']):d for d in ds[m] if d['experiment']==2 and d['reasoning']==t and d['prompt_condition']==p and d['status']=='VALID'} for p in ['P0','P1']]
            ids=set(maps[0])&set(maps[1]);c=Counter((maps[0][i]['strict_answer_marker'],maps[1][i]['strict_answer_marker']) for i in ids)
            pair.append([m,t,len(ids),c[False,True],c[True,False],c[True,True],c[False,False]])
    lines += table(['Model','Inference','Common valid','New probe from P1.','Disappearing from P1.','Both are detectives.','They don\'t have either.'],pair)
    lines += ['## 5Based citation and input isotope', '']
    lines += table(['Model','Valid responses','Based on empty array','More than one quote is inconsistent.'],[[m,len(z),sum('EMPTY_EVIDENCE' in d['tags'] for d in z),sum('QUOTE_NOT_EXACT_SUBSTRING' in d['tags'] for d in z)] for m in models if (z:=[d for d in ds[m] if d['status']=='VALID'])])
    lines += ['A quotation mismatch means the exact string is absent from the context; it does not by itself establish hallucination. Conversely, an exact quotation does not guarantee correct calculation or reasoning.', '',
        'Variant 700of 350The answer is: 50Q/C and experimentation on the production criteria for items. 1 The Q/C is different at the string level.0006The difference in the prefix, the spacetime, and the dot sequence of the front sentence is verified. 50It\'s not that items are equals in meaning. 1→2 Change can mix the effects of the text with other than the transformations.', '',
        'IC-source 200The parent before/after of the current table is the parent position of the connected value. The original A/B distinguishes the claim that assigned the source and retains its ID. The position and the source effect are not interpreted the same. The automatic PASS of all variations passes the final text check and is not a complete proof of the meaningful improbability/impossibility of an improbable answer.', '',
        '## 6. raw response cases and measures', '',
        '[Case by case review](CASE-STUDIES.md)Read the entire failure saved in the model-by-model document below.', '',
        *[f'- [{m} The failure of the algorithm.{m}-failures.md)' for m in models], '',
        '1.Printing call sign front negative sign missing: correction; recollection completed. raw response and previous result preservation.',
        '2.Number, null, required field absence instead of string: return format problems and separate content problems. Do not automatically convert raw response to normal response.',
        '3Multi-digit answer: We need to improve the subsequent extraction to distinguish between the annular, intermediate, and maximum values. This time, keep the undervalued.',
        '4Cut the power. 37The final answer is not complete, so I don\'t judge it with a negative/obvious response.',
        '5.Ubo Expression: Existing answer-only detection is missing due to instances where only descriptions have a ubo or nulls are returned. Expanded observations are provided together but not used accurately.',
        '6. Meaning evaluation and input homogeneity: 50The strong model of the Uey-Yabo success rate argument is in place before reviewing whether there is a fundamental difference and whether there is any real answer.', '',
        '## Reproduction and scope', '',
        '`PYTHONPATH=src .venv/bin/python -m finarch.experiments.02-analysis.legacy.content-analysis.analysis --run reports/experiments-run/20260920-exp-003`', '',
        'This analytics program does not call the API. 6,000The content review of the representative case records the entire case in CASE-STUDIES.md, and does not claim to have performed the numerical significance check.', '']
    build_cases = __import__('finarch.experiments.02-analysis.legacy.content-analysis.case_studies', fromlist=['build']).build
    build_cases(root)
    write_text(root / 'ANALYSIS.md', '\n'.join(lines))
    write_text(output / 'README.md', '# The analysis of the results\n\n1. ../ANALYSIS.md: The range of the statistics, the analysis and the analysis.\n2. ../CASE-STUDIES.md: Representative response case against the basis.\nModel name-failures.md: Failure response prime and actual Q/C response.\n4. response-diagnostics.jsonl: 6,000Reproductive diagnosis of the items response.\n5. before-currency-sign-fix/: Number extract and correct the previous set.\n\nanalysis.py generates compilation and guidance documents, but HTML doesn\'t.\n')
    event(root,'RESPONSE_ANALYSIS_COMPLETED',responses=len(diagnostics),failures=sum(d['status']!='VALID' for d in diagnostics),new_model_calls=0)
    print(json.dumps({'responses':len(diagnostics),'failures':sum(d['status']!='VALID' for d in diagnostics)}))


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--run',required=True)
    main(parser.parse_args().run)
