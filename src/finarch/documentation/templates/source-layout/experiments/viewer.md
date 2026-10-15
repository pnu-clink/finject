# 실험 뷰어 서버·내보내기

[문서의 단계·요구·실행 흐름](../../../../docs/02-experiments/README.md) · [전체 소스 구조](../../../../docs/01-dataset/90-operations/05-source-layout.md)

이 폴더는 위 문서 단계의 실행 코드를 소유합니다. 결과의 물리 경로는 기존 run 계약을 따릅니다.

[사분면 비교](http://127.0.0.1:8894/?tab=quadrants)는 현재 서버의 결과 폴더에서 실제 A02 집계를 읽는 추가 메뉴입니다. 공통 표시 소스는 [research_ic_value_quadrant.py](../../documentation/research_ic_value_quadrant.py)와 [사분면 템플릿](../../documentation/templates/research/ic-value-quadrant.fragment.html)입니다. 메모리 안에서 HTML을 만들며 결과 폴더·독립 HTML·원응답을 쓰지 않습니다. [EV23 파일별 흐름과 검증](../../../../log/viewer-experiments-quadrants-20261003/README.md).

|파일|역할|
|---|---|
|[paths.mjs](paths.mjs)|프로젝트·결과 폴더·브라우저 자산 경로의 기준|
|[repository.mjs](repository.mjs)|선택 실행의 저장 결과·원응답·검사 연결 및 EV27 근거 타당성 요약·20쌍 조회|
|[grounding-reader.mjs](grounding-reader.mjs)|EV27.1 기존 A02 pair·판정의 원자료 해시·부모·조건·분모 확인; 새 판정 없음|
|[progress.mjs](progress.mjs)|분석 요청별 완료·실행 중·대기·오류 건수, 처리시간, 실제 동시 호출 수·한도·CPU 이력 집계|
|[input-flow.mjs](input-flow.mjs)|원천·복사 경로와 public/private·요청·호출·검사 파일의 흐름 연결; 실행 밖의 원천은 경로만 표시|
|[server.mjs](server.mjs)|조회 API·정적 자산 제공, 서버 준비와 브라우저 열기|
|[outcome-comparison.mjs](outcome-comparison.mjs)|원천별 저장 결과 또는 final PASS 합본의 해시 검증·G/R별 건수·미완료 조회; LLM 호출 없음|
|[quadrants.mjs](quadrants.mjs)|여러 회차 비교의 Python 조회·조회별 HTML 연결·해시 CSP·수집 범위 API|
|[quadrants.py](quadrants.py)|공통 생성기의 출처·동일 입력·분모 검사 재사용, 원자료 보존 확인, 파일 쓰기 없는 화면 생성|
|[server.py](server.py)|세 영역에 공통인 Python 모듈 실행 형식으로 Node 서버 시작|
|[export-html.mjs](export-html.mjs)|한 실행의 자료와 화면 자산을 단일 오프라인 HTML로 묶기|
|[viewer.py](viewer.py)|이전 데이터셋 통합 화면의 실험 조회 API 호환 코드|

## 진행 대시보드 · EV19

[대시보드 열기](http://127.0.0.1:8894/?tab=progress)에서 run과 분석 단계를 선택합니다. 브라우저 자산은 [progress.html](../../../../viewer/experiments/progress.html), [progress-dashboard.mjs](../../../../viewer/experiments/progress-dashboard.mjs), [progress-dashboard.css](../../../../viewer/experiments/progress-dashboard.css)가 담당합니다. 파일별 흐름·집계 기준은 [실험 뷰어 안내](../../../../viewer/experiments/README.md#진행-대시보드--ev19)를 읽으세요.

진행 조회는 전체 응답·manifest를 다시 읽지 않고 상태·시간·스케줄러·이벤트 파일만 읽습니다. 이 API는 읽기 전용이며 LLM 호출·재시도·실행 제어를 하지 않습니다. [로컬 검사와 실제 화면 확인](../../../../reports/run/20260927-experiment-source-layout/progress-dashboard-verification.json)을 함께 제공합니다.

## 화면 언어 · UI-L05

`server.mjs`는 [공통 한·영 자산](../../../../viewer/shared/README.md)을 정적 경로로 제공하고, `export-html.mjs`는 같은 JS·CSS를 HTML에 인라인한 뒤 CSP 해시를 다시 계산합니다. `initial_view.lang`은 내보낼 때 선택한 언어입니다. 내장 자료 조회와 언어 전환은 오프라인이며 새 모델 호출을 하지 않습니다. [확인 자료와 검사 범위](../../../../outputs/viewer-i18n-20261002/README.md).

## 근거 타당성 · EV27

[근거 타당성 화면의 계약·파일별 흐름](../../../../docs/02-experiments/02_analysis/02_comparison/02-response-grounding-review.md#근거-타당성-화면--ev27)을 따릅니다. `/api/runs/:run/grounding-pairs`는 기존 A02의 두 판정·pair 집계를 검증하고 요약 또는 20쌍의 메타만 반환합니다. 사분면을 펼친 후 기존 case API로 정확한 원본/변형 응답·이유·인용을 조회합니다. `viewer/experiments/grounding-model.mjs`의 고정 분모·필터·페이지 함수는 서버와 단일 HTML Export가 함께 사용합니다. 저장 pair 부재·오래된 해시를 새 판정으로 채우지 않으며 새 LLM 호출이나 pipeline 재집계를 실행하지 않습니다.
