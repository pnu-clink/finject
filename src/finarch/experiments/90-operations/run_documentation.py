"""Generate stage navigation from one template and actual saved status."""
from pathlib import Path

store = __import__('finarch.experiments.90-operations.storage', fromlist=['*'])
layout = __import__('finarch.experiments.90-operations.run_layout', fromlist=['*'])


def render(root, only=None):
    root = Path(root)
    if not layout.ordered(root):
        return
    template = (store.PROJECT / 'src/finarch/experiments/templates/ordered-stage-readme-template.md').read_text()
    config = store.read(root / 'config.json')
    configuration = __import__('finarch.experiments.02-analysis.configuration', fromlist=['*'])
    analysis = configuration.read(root)
    backend = analysis.get('backend', 'disabled')
    selected = analysis.get('backends', {}).get(backend, {})
    prompt_links = ', '.join(f'[{path.name}]({path.name})' for path in
                            (layout.prompt_file(layout.definition(root), condition) for condition in layout.PROMPT_FILES))
    stages = [
        ('00_input', '00 Input', '문제 입력과 평가 참조를 분리합니다.',
         'I00.01 receive_results → I00.02 check_delivery → I00.03 bind_edit_provenance. dataset.select()가 전달 자료와 변경 이력을 확인해 public/private를 저장합니다. 기존 run의 이력 보강은 experiments/00-input/edit_provenance.py의 attach(run)가 실행합니다.',
         '- [public.jsonl](public.jsonl): Q/C·precision·연결 ID. 모델 입력은 Q/C·precision만 사용합니다.\n- [private.jsonl](private.jsonl): 정답·유형·제작 근거·출처·edit_provenance. 평가·분석 전용입니다.\n- original_external_knowledge가 있으면 원본 제작 시 확인된 외부사용 분류입니다. 변형에 복사된 값은 원본의 라벨이며 변형 자체의 재판정이 아닙니다. used=false는 확인 조건 미충족이지 비사용의 증명이 아닙니다. A01→A02→A03에만 전달하며 풀이 모델에는 보내지 않습니다.\n- edit_provenance.steps: 원본 → 값 변경 → 출처 추가의 순서·편집 위치·전후 문자열·Q/C 해시. VERIFIED는 편집 복원의 일치이며 의미 정답 판정이 아닙니다.\n- 뷰어의 입력 C: 값은 초록, 출처 A는 분홍, 출처 B는 빨강. 삭제한 문자열은 변경 기록에만 표시합니다.\n- [events.jsonl](../events.jsonl)의 EDIT_PROVENANCE_ATTACHED: 기존 자료 보강 전후 해시·보존 확인·모델 호출 0건. public·요청·원응답·점수는 수정하지 않습니다.',
         'dataset.py / edit_provenance.py', 'dataset results 00~07 · 변경 이력', '선정·전달·편집 복원 확인', 'public Q/C·precision / private 평가·변경 이력'),
        ('01_evaluation', '01 Evaluation', '대상 모델에게 풀이를 요청하고 원응답과 형식 검사를 저장합니다.',
         'E01 준비 → E02 요청 → E03 LLM 실행 → E04 형식 검사.',
         '\n'.join(f'- [{name}](./{name}/README.md)' for name in ('01_preparation', '02_request', '03_execution', '04_validation')),
         'pipeline.py', 'public·실험 조건', 'LLM 풀이·응답 수집', '원응답·형식 상태'),
        ('01_evaluation/01_preparation', 'E01 Preparation', '실험 대상과 모델·조건을 확정합니다.',
         'E01.01 문항 선정 · E01.02 public/private 분리 · E01.03 설정 동결. 01-preparation/prepare.py가 실행합니다.',
         '- [config.json](../../config.json)의 evaluation: 대상·모델·조건·호출 방식.\n- [events.jsonl](../../events.jsonl)의 INPUT_SELECTION: 선정·제외 근거.\n- [run-readme-template.md](run-readme-template.md), [model-readme-template.md](model-readme-template.md): 이 run의 안내 문서 생성 양식. LLM에 보내지 않습니다.',
         'settings.py / pipeline.py / dataset.py', 'schedule/run·프로필·dataset', 'E01 대상·조건 확정', '설정·선정 기록'),
        ('01_evaluation/02_request', 'E02 Request', '실제로 보낼 풀이 지시와 문제 입력을 고정합니다.',
         'E02.01 prompt_and_schema · E02.02 public_input · E02.03 model_manifest. 02-request/prepare.py가 실행합니다.',
         '- [common.md](common.md): 공통 필드 안내.\n- ' + prompt_links + ': 조건별 지시.\n- [response.schema.json](response.schema.json): 공통 응답 형식.\n- [plan.json](plan.json): 요청 수·예상 비용.\n' + '\n'.join(f"- [{m['key']}/manifest.jsonl]({m['key']}/manifest.jsonl): 문항·조건·실제 전송 입력의 단일 실행 기준." for m in config['evaluation']['models']),
         'pipeline.py / answer_format.py', 'public·prompt·schema', 'E02 요청 고정', '모델별 manifest'),
        ('01_evaluation/03_execution', 'E03 Execution', '대상 LLM을 호출하고 실제 전송·원응답·사용량을 보존합니다.',
         'E03.01 LLM_call · E03.02 collect_raw_response. openai_batch.process(), anthropic_batch.process(), gemini_batch.process() 또는 providers.call()이 실행합니다.',
         '\n'.join(f"- [{m['key']}/]({m['key']}/): batches/의 Batch 전송·수신, calls/의 문항별 원응답과 시도 기록." for m in config['evaluation']['models']),
         'openai_batch.py / anthropic_batch.py / gemini_batch.py / providers.py', '고정 요청 manifest', 'E03 LLM 풀이', '원응답·사용량'),
        ('01_evaluation/04_validation', 'E04 Validation', '응답 형식을 검사하고 미실행·실패·통과를 구분합니다.',
         'E04.01 파싱 → E04.02 response_errors → E04.03 reporting.build → E04.04 numeric_validation.build.',
         '- [REPORT.md](REPORT.md) · [summary.json](summary.json): 전체 풀이 수집·형식 검사·비용.\n- numeric-comparisons.jsonl: 수집 후 기존 정답 기준의 숫자 비교·미평가 이유.\n' + '\n'.join(f"- [{m['key']}/README.md]({m['key']}/README.md): 모델별 results.jsonl·summary.json." for m in config['evaluation']['models']),
         'answer_format.py / reporting.py / numeric_validation.py', '원응답·schema·평가 참조', 'E04 형식·숫자 검사', '결과 목록·통과/실패·숫자 비교'),
        ('02_analysis', '02 Analysis', f"선택한 분석 방식: {backend} · {selected.get('model', '미설정')} · {selected.get('reasoning_effort', '미설정')}. 대상 모델 설정과 독립적입니다.",
         'A01 결과 취합 → A02 관계 비교 → A03 연구 해석·개선안 토의.',
         '\n'.join(f'- [{name}]({name}/README.md)' for name in ('01_results', '02_comparison', '03_research')) + '\n- config.json: 별도 동결한 Analysis 설정이 있으면 사용합니다. 그렇지 않으면 run 루트 config.json의 analysis를 읽습니다.',
         '02-analysis/pipeline.py / llm_backend.py', 'Q/C·원응답·E04·private', '결과 취합·관계 분석', '응답 행·비교·연구 해석'),
        ('02_analysis/01_results', 'A01 Results', '전체 계획 응답과 기존 평가 결과를 연결합니다.',
         'A01.01 collect_saved_results → A01.02 attach_existing_context → A01.03 record_response_rows. results.build()가 실행합니다.',
         '- responses.jsonl: 모든 계획 응답·숫자 평가·제작 메타·원응답 연결. 원본 외부사용 분류가 있으면 private에서 함께 연결합니다.\n- state.json: 원천 파일 해시·취합 상태. 누락·실패 응답도 전체 분모에 남깁니다.',
         '01-results/results.py', '요청·원응답·E04·private', 'A01 Python 취합', 'responses·state'),
        ('02_analysis/02_comparison', 'A02 Comparison', '동일 문항의 조건 차이와 반례를 비교합니다.',
         'A02.01 pair_conditions → A02.02 aggregate_relations → A02.03 compare_variant_patterns → A02.04 LLM_interpret_patterns → A02.05 record_comparisons. comparison.py가 집계하고, pipeline.comparison_requests() → llm_backend.run()이 해석을 요청하며, pipeline.collect_interpretations()·update()가 해석·coverage·상태를 기록합니다.',
         '- comparisons.json: Python 집계·대응 관계·분모. 원본 외부사용 분류별 기술 집계는 별도 축입니다.\n- interpretations.jsonl: 정확 인용과 응답 ID를 검사한 LLM 해석.\n- coverage.json: 계획 문항·성공·실패·미해석.\n- manifest.jsonl → calls/ → results.jsonl · state.json: 요청·원응답·상태.',
         '02-comparison/comparison.py / pipeline.py / llm_backend.py', 'A01 응답·미평가', 'A02 조건·유형·반례 비교', 'comparisons·interpretations·coverage'),
        ('02_analysis/03_research', 'A03 Research', '수집한 비교 근거의 관찰과 한계를 정리합니다.',
         'A03.01 assemble_evidence: pipeline.research_requests() → A03.02 LLM_synthesize_findings: llm_backend.run(). A03.03 discuss_improvements는 사용자와 토의할 안건을 남깁니다. A03.04 publish_findings: pipeline.collect_findings() → research.finish()가 findings.json·안내 문서를 만듭니다. 보고를 생성해도 사용자 결정 전에는 USER_DISCUSSION_PENDING이며 후속 실험을 자동 실행하지 않습니다.',
         '- manifest.jsonl → calls/ → results.jsonl · state.json: 선택한 분석 모델의 실제 요청·원응답·검사.\n- findings.json: 해석·근거 ID·반례·대안·한계·미실행 토의.\n- findings.md: 위 결과의 안내 문서. 작성 전에는 미완료입니다.',
         'pipeline.py / llm_backend.py / 03-research/research.py / contracts.py', 'A01 근거·A02 비교', 'A03 비판적 해석', 'findings·state·README'),
    ]
    state = store.read(root / 'state.json', {})
    # Usage is current documentation; keep the run's frozen definition templates intact.
    root_readme = root / 'README.md'
    usage_heading = '## 사용법과 재개'
    usage_template = store.PROJECT / 'src/finarch/experiments/templates/ordered-run-readme-template.md'
    if only is None and root_readme.exists():
        _, separator, usage = usage_template.read_text().partition(usage_heading)
        if separator:
            current = root_readme.read_text().partition(usage_heading)[0].rstrip()
            store.write_text(root_readme, current + '\n\n' + usage_heading +
                             usage.format(run_id=root.name, run_path=str(root)))
    for relative, title, purpose, steps, files, code, incoming, step, outgoing in stages:
        if only is not None and relative not in only:
            continue
        selection = store.read(layout.inputs(root) / 'selection.json', {}) if relative == '00_input' else {}
        if selection.get('generated_format'):
            generated_template = Path(__file__).resolve().parents[1] / 'templates/generated-input-readme.md'
            store.write_text(root / relative / 'README.md', generated_template.read_text().format(
                source=selection['generated_path'], originals=selection['originals'],
                variants=selection['variants'], analysis_status=selection['analysis_metadata_status'],
                gaps=len(selection['analysis_metadata_gaps'])))
            continue
        status = f"풀이 수집 상태: `{state.get('status', 'PREPARED')}`. 분석 완료 여부는 각 분석 폴더의 실제 결과와 state.json을 확인합니다."
        if config.get('registration', {}).get('mode') == 'COMPLETED_VLLM_STAGE':
            status += '\n\n완료된 vLLM 실험을 기존 run 구조로 등록한 자료입니다. 등록 명령은 pipeline.py register-a100-stage이며 모델을 재호출하지 않습니다.'
            if relative in ('00_input', '01_evaluation/01_preparation', '01_evaluation/02_request'):
                code = 'a100/register_stage.py'
                steps = '등록 원본 해시 확인 → 동일 public/private 연결 → 실제 원격 요청 manifest·지시·스키마 동결. 새 문제나 요청을 생성하지 않습니다.'
            elif relative == '01_evaluation/03_execution':
                code = 'a100/register_stage.py / a100/collect.py'
                steps = '기존 원격 원응답·payload 해시 확인 → source-stage 원본 보존 → calls 문항별 시도 기록 연결. 대상 모델 재호출은 0건입니다.'
                files += '\n- 모델별 source-stage/: 원격의 원응답·취합본·telemetry·완료 상태를 그대로 보존합니다.'
            elif relative.startswith('02_analysis'):
                status += '\nAnalysis는 사용자 중지 상태이며 이 등록 과정에서 실행하지 않았습니다.'
        if relative == '02_analysis' and (root / relative / 'scheduler.json').exists():
            files += '\n- [scheduler.md](scheduler.md) · [scheduler.json](scheduler.json): 동시 호출 한도·CPU·실행 및 대기 건수.\n- [timing.md](timing.md): 단계별 실제 시간과 병목.'
        queue = state.get('queued_execution', {})
        if relative == '01_evaluation/03_execution':
            overrides = store.read(root / 'runtime-overrides.json', {})
            for model_key, override in overrides.get('models', {}).items():
                budget = override.get('output_budget')
                if budget:
                    files += (f"\n- `{model_key}`: 새 요청 출력 상한 {budget['base_output_tokens']:,}토큰(추론 포함). "
                              f"실제 length 종료만 이전 상한의 2배로 재시도하고 {budget['max_output_tokens']:,}토큰에서 멈춥니다. "
                              "[runtime-overrides.json](../../runtime-overrides.json)에 승인과 정책, 각 attempt의 request.json·started.json·result.json에 실제 상한과 근거를 기록합니다. "
                              "동결 요청과 이전 시도는 보존하며 전달 불확실·일반 형식 실패는 재호출하지 않습니다.")
        if relative == '01_evaluation' and queue.get('status') == 'WAITING_FOR_ANALYSIS':
            status += f"\n\n사용자 승인으로 `{queue['after_run']}`의 Analysis 완료 후 Native Batch Evaluation을 진행합니다. 현재는 선행 분석 완료를 기다립니다. Haiku Analysis는 중지 상태입니다."
        store.write_text(root / relative / 'README.md', template.format(**locals()))
