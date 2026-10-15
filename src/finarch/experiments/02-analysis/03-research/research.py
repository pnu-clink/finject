"""Validate references, record current-session findings, and render the same data."""
import argparse
from collections import Counter
from pathlib import Path

collect = __import__('finarch.experiments.02-analysis.01-results.results', fromlist=['*'])
contracts = __import__('finarch.experiments.02-analysis.contracts', fromlist=['*'])
backend = __import__('finarch.experiments.02-analysis.llm_backend', fromlist=['*'])
store = collect.store


def finish(root, *, finalize=True):
    root = Path(root).resolve()
    collect.verify_reuse(root)
    base = root / collect.ANALYSIS
    rows = collect.unique(store.rows(base / '01_results/responses.jsonl'), 'response_id', 'RESPONSE')
    comparisons = store.read(base / '02_comparison/comparisons.json')
    if comparisons['response_rows_sha256'] != store.file_hash(base / '01_results/responses.jsonl'):
        raise ValueError('COMPARISONS_SOURCE_CHANGED')
    interpretations = store.rows(base / '02_comparison/interpretations.jsonl')
    findings = store.read(base / '03_research/findings.json')
    if findings['run'] != root.name:
        raise ValueError('FINDINGS_RUN_MISMATCH')
    contracts.validate_interpretations(interpretations, rows)
    contracts.validate_findings(findings, interpretations)
    refs = sorted({ref for item in interpretations for ref in item['response_ids']})
    evidence_files = ['02_analysis/01_results/responses.jsonl', '02_analysis/02_comparison/comparisons.json']
    config = backend.analysis_config.read(root)
    current_session = config.get('execution_mode') == 'current_session'
    calls = []
    reviews = __import__('finarch.experiments.02-analysis.02-comparison.response_assessments', fromlist=['*'])
    assessment_summary = store.read(base / '02_comparison/response-assessment-summary.json')
    if assessment_summary and reviews.gate(assessment_summary)['blocked']:
        raise ValueError('INCOMPLETE_RESPONSE_REVIEWS')
    if current_session:
        backend.record(root, '02_comparison', contracts.INTERPRETATIONS, interpretations, evidence_files, refs)
        backend.record(root, '03_research', contracts.FINDINGS, findings,
                       evidence_files + ['02_analysis/02_comparison/interpretations.jsonl'], refs)
    else:
        for stage in ('02_comparison', '03_research'):
            folder = base / stage
            for req in store.rows(folder / 'manifest.jsonl'):
                result = backend.latest(folder, req)
                if result and result['status'] == 'VALID' and contracts.validate_response(result['response'], req):
                    raise ValueError('SAVED_ANALYSIS_VALIDATION_CHANGED:' + stage)
                if not result or result['status'] != 'VALID':
                    if stage != '02_comparison' or assessment_summary is None:
                        raise ValueError('INCOMPLETE_ANALYSIS_CALLS:' + stage)
                    # A02 unavailable targets are retained without fabricating a valid judge response.
                    if any(row['variant'] != 'ORIGINAL' and contracts.review_status(row, req) == 'COMPLETED'
                           for row in req['input']['responses']):
                        raise ValueError('INCOMPLETE_ANALYSIS_CALLS:' + stage)
                calls.extend(store.read(path) for path in backend.attempts(folder, req))
    coverage = {'structured_responses': len(rows), 'cited_response_count': len(refs),
                'cited_response_ids': refs, 'interpretations': len(interpretations),
                'categories': dict(Counter(i['category'] for i in interpretations)),
                'independent_question_reviews': 0,
                'scope': 'All structured results aggregated; cited examples interpreted. Not exhaustive semantic adjudication.'}
    assessment_summary = store.read(base / '02_comparison/response-assessment-summary.json')
    if assessment_summary:
        coverage['response_assessments'] = assessment_summary['overall']
        coverage['scope'] = 'Selective pattern observations and separately recorded per-variant LLM response assessments; see assessment coverage.'
    common = {'status': 'COLLECTED', 'method': collect.METHOD, 'backend': config['backend'],
              'execution_mode': 'current_session' if current_session else 'codex_cli' if config['backend']=='codex' else 'openai_batch',
              'separate_model_invocation': not current_session,
              'external_model_calls': len(calls), 'new_target_model_calls': 0,
              'analysis_model': config.get('backends', {}).get(config['backend'], {}).get('model'),
              'usage_records': sum(bool(c.get('usage')) for c in calls),
              'api_cost_estimate_usd': ((sum(c['token_cost_estimate_usd'] for c in calls)
                  if all(c.get('token_cost_estimate_usd') is not None for c in calls) else None)
                  if config['backend']=='api' else 0),
              'completed_at': store.now(), 'coverage': coverage}
    for stage in ('02_comparison', '03_research'):
        previous = store.read(base / stage / 'state.json', {})
        store.write(base / stage / 'state.json', previous | common | (
            {'findings': len(findings['findings']), 'discussion_status': 'USER_DISCUSSION_PENDING'} if stage=='03_research' else {}))
    counts = comparisons['overall']
    lines = []
    for f in findings['findings']:
        ko = f['display_ko']
        lines.extend([f"## {f['id']} · {ko['title']}", '', ko['claim'], '',
                      '**가능한 다른 설명:** ' + ko['alternatives'], '',
                      '**한계:** ' + ko['limitation'], '', '**판정:** ' + ko['decision'], '',
                      '근거 해석: ' + ', '.join(f['interpretation_ids']) + '.', ''])
    lines += ['## 개선 토의 안건 — 실행 전', '']
    for d in findings['discussion']:
        lines += [f"- **{d['id']} {d['display_ko']['proposal']}** — {d['display_ko']['reason']}"]
    lines += ['', '## 실제 응답으로 돌아가기', '',
              '|해석|관찰과 한계|응답 근거|', '|---|---|---|']
    for i in interpretations:
        ko = i.get('display', i.get('display_ko', i))
        links = []
        for ref in i['response_ids']:
            row = rows[ref]
            label = f"{row['case']} {row['variant']} {row['prompt_condition']}/{row['reasoning']}"
            links.append(f"[{label}](../../{row['result_path']})")
        lines += [f"|{i['id']} · {ko['title']}|{ko['observation']} {ko['limitation']}|{'<br>'.join(links)}|"]
    execution_note = ('현재 Codex 대화의 분석을 기록했습니다. 별도 호출 0회.' if current_session else
                      f"{common['execution_mode']} · {common['analysis_model']} · 분석 시도 {len(calls)}회. 원응답은 calls에 보존합니다.")
    collect.render(root, '03_research', source=comparisons['evaluation_source'], findings=len(findings['findings']), cited=len(refs), execution_note=execution_note)
    template = (store.PROJECT / 'src/finarch/experiments/templates/results-findings.md').read_text()
    store.write_text(base / '03_research/findings.md', template.format(run=root.name,
        source=comparisons['evaluation_source'], total=counts['planned'], valid=counts['format_valid'],
        numeric=counts['numeric'], null=counts['null'], originals=counts['original_results'],
        cited=len(refs), observations=len(interpretations), body='\n'.join(lines), execution_note=execution_note,
        original_count=len({r['case'] for r in rows.values()})))
    pairs = sum(g['planned_pairs'] for g in comparisons['paired_groups'])
    collect.render(root, '02_comparison', source=comparisons['evaluation_source'], planned=len(rows), pairs=pairs, status='응답 관계 해석 저장 완료')
    collect.render(root, 'analysis', source=comparisons['evaluation_source'], status='A01·A02·A03 완료 · 개선안 사용자 토의 대기')
    if 'evaluation_reuse' in store.read(root / 'config.json'):
        collect.render(root, 'run', source=comparisons['evaluation_source'], status='Analysis 완료 · 개선안 사용자 토의 대기', planned=len(rows))
    state = store.read(root / 'state.json')
    state['analysis'] = common | {'status': 'COMPLETE' if finalize else 'RUNNING',
        'stage': 'A03' if finalize else 'A04', 'discussion_status': 'USER_DISCUSSION_PENDING'}
    store.write(root / 'state.json', state)
    store.event(root, 'RESULTS_FOCUSED_ANALYSIS_COMPLETED' if finalize else 'A03_RESEARCH_COLLECTED', **coverage, findings=len(findings['findings']),
                new_target_model_calls=0, external_model_calls=len(calls), source_run=comparisons['evaluation_source'])
    collect.verify_reuse(root)
    return common


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    print(finish(parser.parse_args().run))
