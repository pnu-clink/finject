# {{title}}

{{current_intro}}

완료한 기존 원응답 진단은 [문제·개선 계획](../../../../docs/02-experiments/04-comparison/01-improvement-plan.md)과 [실제 검토 근거](03-research/intent-review-evidence.json)에 보존합니다. 원문 {{review_cases}}개에서 고른 응답 {{review_responses}}개와 근거 파일 {{review_files}}개의 해시를 연결했습니다. 보고서 생성 자체의 새 모델 호출은 **0회**입니다.

기존 응답 형식(파일 식별명 `FinancialAnswerMagnitudeV4`)과 변경해 둔 응답 형식(파일 식별명 `FinancialAnswerV6`; 제공자가 반환한 새 응답 {{successful}}건)을 구별합니다. 이 이름은 파일에서 응답 규약을 구별하는 식별자이며 모델 버전이나 여섯 번째 실험을 뜻하지 않습니다. 이하 제목과 설명에서는 기존 형식·변경해 둔 형식으로 부릅니다. 변경안을 저장하고 로컬 검사를 통과한 사실과 실제 모델 응답이 좋아졌다는 판단은 다릅니다.

{{run_status}}

## 읽는 순서

숫자로 먼저 살펴보려면 [종합 현황 대시보드](http://127.0.0.1:8895/dashboard/01-overview/)와 [문항 분석 대시보드](http://127.0.0.1:8895/dashboard/02-explorer/)를 사용합니다. 산점도·표·실제 응답을 연결하며 [구현과 읽는 방법](../../../../viewer/dashboard/README.md)에 범위를 기록합니다.

1. [문제·개선 계획](../../../../docs/02-experiments/04-comparison/01-improvement-plan.md): 기존 실험의 문제, 변경안의 한계, 다음 검토 제안
2. [실제 검토 근거](03-research/intent-review-evidence.json)와 [작업 보고서](REPORT.md): 원응답·인용·해시, 완료 범위와 미검증 사항
3. [기존 Luna 원응답 분석](01-baseline/analysis.md)과 [실제 사례](01-baseline/cases.md)
4. [논문 비교 축과 대응쌍](03-research/analysis.md)
5. [실험 전체 흐름](../../../../docs/02-experiments/README.md): 정의 → 입력 → 요청·호출 → 검사 → 비교
6. [A100 읽기 시점 자료](02-a100/README.md)
7. [{{run_link_label}}](../../experiments-run/{{run_id}}/README.md): 동결 요청, 저장된 상태와 실제 호출 기록

## 파일 역할

|경로|역할|
|---|---|
|`status.json`|작업 상태·새 실행 경로·사용량 보존 기준|
|`api-blocker.json`|exp-004의 과거 API 차단 이력. 새 run의 현재 상태와 구별|
|`01-baseline/`|기존 응답 형식의 원응답과 exp-004 보조 비교. 기존 점수는 보존|
|`02-a100/`|읽기 전용으로 가져온 원격 보고와 경로·해시|
|`03-research/intent-review-evidence.json`|검토한 기존 원응답·질문·인용 일치 관찰과 근거 파일 해시|
|`03-research/`|기존 응답의 의도 대응 검토, 동일 원문별 P0/P1 대응표와 추론 조건의 차이|
|`04-validation/`|로컬 검사·코드/문서 확인·화면 확인 기록|
|`quota-evidence.json`, `quota-preflight.json`|이전에 저장한 한도 조회·실행 조건 이력. 현재 검토에서 새로 조회하지 않음|
|`documentation.json`|공통 뷰어가 읽는 현재 문서·보고서 색인|
|`events.jsonl`|이 작업의 보고서 갱신과 상태 기록|

[공통 뷰어](http://127.0.0.1:8895/?run=20260923-experiment-improvement)에서 이 실행을 선택해 실제 최신 파일을 읽습니다. 결과 폴더용 HTML은 만들지 않습니다. `{{run_id}}`의 수집·미실행 상태는 [실험 뷰어](http://127.0.0.1:8894/?run={{run_id}}&tab=overview)의 같은 화면에서 확인합니다.

두 프롬프트에 공통 JSON을 주는 것은 표현 조건을 맞추려는 조치이며, 그 구조가 모델 행동에 주는 영향이 0임을 보장하지 않습니다. 이미 저장한 변경안과 새 필드·후속 비교의 제안을 구별하고, 실제 효과는 성공 응답을 확보한 뒤에만 판단합니다.

README는 `src/finarch/experiments/02-analysis/legacy/comparison/improvement-report-template.md`에서 생성합니다. 보고서를 다시 만들려면 `PYTHONPATH=src .venv/bin/python -m finarch.experiments.02-analysis.legacy.comparison.improvement_report`를 실행합니다. 에이전트의 파일·화면 확인과 사용자 검토 완료는 구분합니다.
