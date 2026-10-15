# QI06 1차 응답 오프라인 선별 — {run_id}

전체 {records}건 = 완료 {COMPLETE} + 잘림 {TRUNCATED} + 전송오류 {TRANSPORT_ERROR} + 스키마오류 {SCHEMA_ERROR} + 누락 {MISSING}입니다. 잘림 중 raw content null은 {length_null_content}건입니다. 새 API 0회입니다.

## 읽는 순서와 파일 역할

1. `summary.json`: 실행 상태는 전체 {records}건이 분모입니다. cue/숫자 표지는 완료 {COMPLETE}건에서만 계산합니다.
2. `response_screen.json`: 원문 인용·문자 위치·독립 cue·A/B 원값·미평가/생략 이유와 최대 10개 실제 표본 검토입니다.
3. `manifest.json`: 기존 raw/result/request, frozen dataset, legacy first-review, quality-v1 및 생성/QI01 증거의 경로·SHA256입니다. 기록 전후 불변을 확인했습니다.
4. `sidecar-schema.json`: 실제 보고서의 JSON Schema입니다. LLM 응답 스키마가 아닙니다.
5. `events.jsonl`, `checks.txt`: 생성 단계와 별도로 수행한 로컬 검사 로그입니다.

공통 viewer에서 `{run_id}` 실행을 선택합니다. `/api/run?name={run_id}`는 저장 보고서만 읽고, 표의 원자료 링크는 manifest hash를 확인합니다. QI05 및 QI01 보고서도 연결합니다. 별도 결과 HTML은 만들지 않습니다. 브라우저 시각 확인은 메인 담당의 후속 확인이며 파일 생성만으로 화면 확인 완료라고 하지 않습니다.

## 확인한 범위와 제한

충돌 {conflict_cue}, 유보 {reject_cue}, 조건 {condition_cue} 표지는 서로 독립이며 {coexisting_cues}건에서 둘 이상 공존합니다. 합계를 문항 수로 해석하지 않습니다. cue는 의미 판정이 아니며 `however`나 부정문 속 단어도 인용 표지에 포함됩니다.

숫자 단독 추출 {bare_numeric}건, A/B 확정 {ab_resolved}건입니다. A는 원 그래프 출력, B는 변경 plan.execution 값이며 gold와 비교하지 않습니다. 첫 버전은 숫자 단독 문법만 지원합니다. 명시적 최종/조건부 문장과 복수 답 추출은 보류합니다. 출력 단위·정밀도 메타데이터가 없거나 단위 없는 숫자면 UNRESOLVED입니다. 입력 fact 단위로 출력 단위를 추정하지 않습니다.

실제 bounded agent 표본 {manual_samples}건은 실행·표지·추출만 검토했고 의미 확정은 {semantic_adjudicated}건입니다. 불확실한 의미는 UNKNOWN, 잘림은 NOT_EVALUATED입니다. 짝 비교는 이번 범위 밖이므로 분석 가능 여부를 확립한 쌍은 {pair_analysis_eligible}건입니다. 전체 응답 의미 판정·범용 parser·재호출·전수 사람 검토는 구현하지 않았습니다.

QI01 실제 복원 증거가 연결된 {known_invalid_perturbations}건만 perturbation INVALID입니다. 나머지 EA는 UNKNOWN, 원문/reference 타당성은 NOT_REVIEWED입니다. 승인을 타당성 증거로 쓰지 않습니다. 3회 temperature 0 반복은 독립 모델 3개가 아니며 이 보고서는 1회차만 다룹니다.

## 재현

`PYTHONPATH=src .venv/bin/python -m finarch.dataset.03-release.review_first_repeat --source reports/run/20260916-001 --quality-root reports/run/20260916-quality-v1 --output reports/run/새로운-실행명 --samples src/finarch/dataset/checks/fixtures/response-screen-real-samples-v2.json`

기존 output 디렉터리는 거부합니다. 이전 first-review와 quality-v1을 덮어쓰지 않습니다. 원자료 변경은 SNAPSHOT_CHANGED로 중단하며 재시도나 API 호출은 하지 않습니다.
