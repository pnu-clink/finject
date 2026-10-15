# {title}

상태: **{status}** · 대상: 같은 원문 10개에 대해 Claude Haiku 4.5와 Gemini 2.5 Flash-Lite 각 10회

## 읽는 순서

1. `plan.json`: 문항, 조건, 모델·호출 수, 비용 추정과 과학적 해석 범위.
2. `access-preflight.json`: 키 값을 제외한 제공자 접근·캐시 사전 검사 결과.
3. `model-access-check.json`: 프로젝트 번호 제공 전에 새 키로 과금 없는 모델 정보와 로컬 Vertex 설정을 조회한 이력.
4. `vertex-cache-check.json`: 제공받은 Google Cloud 프로젝트의 캐시 설정을 읽기 전용으로 조회한 결과. HTTP 403으로 실제 캐시 상태는 미확인입니다.
5. `vertex-api-key-check.json`: 같은 프로젝트 캐시 설정을 현재 Gemini 키로 조회한 이력. HTTP 401이며 추론 API 적합성은 미검증입니다.
6. [Haiku workspace 호출 테스트](haiku-workspace-call-test.md): 첫 400 오류, 전송 schema 수정, 새 실행 10건의 응답·캐시·숫자 비교 근거.
7. `events.jsonl`: 이 조사 실행의 시간순 기록. 실제 모델 호출과 원응답의 기준 로그는 연결된 실험 run에도 있습니다.
8. [첫 요청 보존본](../../experiments-run/20260924-exp-001/README.md)과 [수정 후 실행](../../experiments-run/{experiment_run}/README.md): 요청·원응답·검사·사용량을 실행별로 구별합니다.
9. [두 모델 나란히 보기](http://127.0.0.1:8894/?run={experiment_run}&tab=models): 같은 원문 10개에 대한 Haiku 응답과 Gemini 미실행 상태를 함께 표시합니다.
10. [Gemini 모델 선택 조사](gemini-model-selection.md): 3.8–1.5의 추론·캐시·JSON 조건과 2.5 미만 Developer API 종료 상태를 비교합니다.
11. [Haiku 4.5 · GPT-6 Luna 옵션 재확인](haiku-luna-controls.md): 호출 전 시점의 공식 추론·캐시 제어 조사입니다.
12. [공통 문서 뷰어에서 호출 보고서 열기](http://127.0.0.1:8893/?run=20260924-experiment-provider-pilot&doc=reports%2Frun%2F20260924-experiment-provider-pilot%2Fhaiku-workspace-call-test.md): `reports/run`의 저장된 문서를 읽습니다.

원문 10개는 데이터셋 제작 자동 검사를 통과한 원문 중 입력 순서의 첫 10개입니다. 일곱 변형은 선별 적격성을 확인하는 데만 사용하며 이번 모델 요청에는 포함하지 않습니다. P0·추론 off만 사용하므로 R0/R1 차이나 변형 유형별 성능을 주장할 수 없습니다. 형식 통과와 숫자 정답 일치는 의미·논리적 타당성 판정과 구별합니다.

이 안내는 `src/finarch/experiments/02-analysis/legacy/comparison/provider-pilot-readme-template.md`에서 생성합니다. 현재 Haiku는 **10건 형식 통과·원본 숫자 9건 일치**, Gemini는 **10건 미실행**입니다. 형식 통과·숫자 일치와 의미 정답은 별개입니다. 공통 `viewer/experiments`는 저장 파일을 그대로 읽으며, 첫 거절 원응답·기존 점수·입력 자료를 소급 수정하지 않습니다.

2026-09-24 모델 조사 결과, 사용자가 요구한 추론·캐시 완전 off는 현재 Gemini Developer API 경로에서 충족되지 않습니다. 후보는 Vertex AI에서 캐시 비활성화가 확인된 프로젝트를 사용하는 2.5 Flash와 Flash-Lite입니다. 제공받은 프로젝트 번호로 설정 조회를 시도했으나 로컬 인증은 HTTP 403, 현재 Gemini 키는 HTTP 401을 받아 캐시 비활성화 여부는 여전히 미확인입니다. 키를 통한 Vertex 추론 적합성은 검사하지 않았고 해당 전송도 아직 구현·검증되지 않았습니다. Haiku는 제공받은 workspace ID로 접근을 복구했으며, 첫 schema 거절 기록과 수정 후 성공한 10건을 별도 실행으로 보존했습니다.
