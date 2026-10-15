# 실험 정리 작업의 로컬 검증 기록

[작업 보고서](../REPORT.md) → [후속 완료 검증](continuation-final-checks.json) → [최신 화면 확인](continuation-final-viewer-checks.json) → 아래 선행 검사 순서로 읽습니다. PASS는 해당 시점의 파일·코드·화면 검사 통과이며 모델 응답의 의미 정답이나 사용자 검토 완료를 뜻하지 않습니다. 분석·검사 자체의 새 API 호출은 0회이고, 실제 실험 호출은 [별도 장부](../03-research/continuation-cost-ledger.json)에 있습니다. 과거 1회 요청·성공0은 exp-004의 API 차단 이력입니다.

[선행 의도 대응 검토](intent-review-checks.json), [초기 문서·보관본 검사](../validation.json), [초기 화면 확인](../ui-review.json)은 당시 기록으로 보존합니다. 최신 실행·표시 결과를 이 과거 기록으로 대신하지 않습니다.

|파일|역할과 확인한 범위|
|---|---|
|[dashboard-frame-checks.json](dashboard-frame-checks.json)|종합 현황 기준 공통 CSS와 상단 틀·색상·폰트·패널 일치, 양쪽 화면의 차트·표·상세 연결을 확인합니다.|
|[dashboard-traffic-checks.json](dashboard-traffic-checks.json)|JENNIFER 형태의 조밀한 관제 화면, 실제 시각·완료량·산점도·연결표·상세와 브라우저 확인 상태입니다.|
|[dashboard-traffic-data.log](dashboard-traffic-data.log)|실제 시작/완료 시각, 시간대·잘못된 날짜·역순·결측 처리와 기존 3,000응답 보존을 확인한 17개 검사입니다.|
|[dashboard-traffic-routes.log](dashboard-traffic-routes.log)|관제형 화면에서도 등록 자산·응답 ID만 읽는 서버 경로를 확인한 4개 검사입니다.|
|[dashboard-traffic-explorer-checks.json](dashboard-traffic-explorer-checks.json)|두 산점도 축·완료 시각 정렬·응답 바로가기·필터·결측 보존·원정밀도 분위수 계산을 대조합니다.|
|[dashboard-traffic-overview-checks.json](dashboard-traffic-overview-checks.json)|분당 완료량·조건별 집계·14개 쌍 비교·산점도 선택 연결·결측 및 0 보존을 실제 3,000응답과 대조한 12개 검사입니다.|
|[dashboard-checks.json](dashboard-checks.json)|대시보드 두 화면의 데이터 집계·선택 연결·실제 브라우저 확인 상태입니다.|
|[dashboard-data.log](dashboard-data.log)|3,000응답의 보존, null·누락·0 구분, 원기록 연결과 읽기 캐시를 검사합니다.|
|[dashboard-routes.log](dashboard-routes.log)|등록된 화면·응답만 읽는 서버 경로와 임의 파일 접근 차단을 검사합니다.|
|[dashboard-overview-checks.json](dashboard-overview-checks.json)|실제 응답의 30조건 집계·14개 P0/P1 비교·비용·미관측 처리·보고서 링크를 대조한 8개 검사입니다.|
|[intent-review-checks.json](intent-review-checks.json)|7원문·20응답의 연결, 근거 파일 33개의 해시 보존, 이번 분석의 새 API 호출 0, 실제 브라우저 확인 범위를 기록합니다.|
|[의도 대응 검토 근거](../03-research/intent-review-evidence.json)|선정 기준·원응답·질문·raw 경로·기존 상태·인용 위치를 연결한 분석 자료입니다. 새 정답·점수는 아닙니다.|
|[python-contract-checks.log](python-contract-checks.log)|V5 보존·V6 표현 규칙·API 어댑터·제한 실행의 26개 로컬 회귀 검사. 원격 API는 모의 처리합니다.|
|[p1-classification-checks.json](p1-classification-checks.json)|현행 P1의 입력 판단·응답 방식 분류, P0 안내 비노출, 공통 schema·과거 동결 정의 보존을 확인합니다. 새 모델 호출은 없습니다.|
|[p1-classification-checks.log](p1-classification-checks.log)|P1 분류 계약과 V6·OpenAI/Anthropic 전송 어댑터의 오프라인 회귀 검사 16개 최종 통과 기록입니다.|
|[p1-classification-checks-initial.log](p1-classification-checks-initial.log)|검사 코드가 저장 manifest의 속성 순서를 전송 순서로 오해한 초기 실패 기록입니다. 검사 기준을 `required` 순서로 수정했습니다.|
|[prompt-layout-checks.json](prompt-layout-checks.json)|2026-09-26 앞선 가독성 편집 당시의 공통 섹션 순서·P1 문장 보존·schema 해시 기록입니다. 이후 P1 분류 변경의 현재 검사는 위 파일을 읽습니다.|
|[prompt-layout-checks.log](prompt-layout-checks.log)|앞선 가독성 편집 당시 V6·OpenAI/Anthropic 오프라인 회귀 검사 15개 통과 기록입니다.|
|[viewer-contract-checks.log](viewer-contract-checks.log)|V4/V5/V6 집계에서 숫자 답 없음과 미평가를 구분하는 뷰어 검사입니다.|
|[documentation-checks.log](documentation-checks.log)|README 템플릿 일치, 진행 순서 채번, 문서 색인·로컬 링크, 기존 문서 79개의 보관 해시를 확인합니다.|
|[prepared-run-checks.json](prepared-run-checks.json)|기록 당시 준비 run의 정의·입력·구현 해시와 3,000요청을 확인한 과거 검사입니다. 현재 실행의 시도 수는 status.json을 따릅니다.|
|[research-contrast-checks.json](research-contrast-checks.json)|미수집·빈 객체·answer 필드 누락을 비교의 미평가로 남기고, 기존 대응표 수치는 유지하는지 확인합니다.|
|[보고서 검증](../validation.json)|보관본·보고서 링크·공용 문서 읽기와 경로 제한을 검사한 결과입니다.|
|[기준선 검증](../01-baseline/verification.json)|기존 입력·원응답·결과 12,008개 파일의 보존 기록입니다.|
|[미수집 응답 회귀 검사](../01-baseline/missing-pair-regression-checks.json)|미수집·파싱 실패·명시적 null이 같은 것으로 집계되지 않는지 확인합니다.|

재현 명령은 프로젝트 루트에서 실행합니다.

```sh
PYTHONPATH=src .venv/bin/python -m unittest finarch.dashboard.checks.test_dashboard_data finarch.dashboard.checks.test_dashboard_routes -v
PYTHONPATH=src .venv/bin/python -m unittest finarch.experiments.checks.test_experiment_contract_v5 finarch.experiments.checks.test_experiment_contract_v6 finarch.experiments.checks.test_experiment_openai_api finarch.experiments.checks.test_improvement_run
python3 src/finarch/documentation/manage.py refresh
python3 src/finarch/documentation/manage.py validate
PYTHONPATH=src .venv/bin/python -m finarch.experiments.02-analysis.legacy.comparison.improvement_report
```

브라우저 확인은 기존 공용 viewer에서 보고서·실험 전체 그림·단계 상세를 직접 열어 수행합니다. 결과 폴더에 별도의 HTML을 만들지 않습니다. 모델 호출과 한도 정책 확인은 이 로컬 검증의 범위 밖이며, 차단된 호출을 PASS로 표시하지 않습니다.
