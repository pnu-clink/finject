# 7조건 사분면 · 두 화면 비교 확인 기록

## 읽는 순서

1. `build-verification.json`: 데이터셋별 공개 입력·후보·문항 집합·조건별 합계·응답 집계·원자료 해시 확인입니다. `revision`이 현재 생성 구성을 구분합니다.
2. `events.jsonl`: 저장 자료를 읽어 독립 HTML을 만든 기록입니다. 실험 이벤트가 아니며 새 모델 호출은 0회입니다.
3. `browser-verification.json`이 있으면 화면·모델 전환·반응형 확인 결과를 읽습니다. 파일이 없거나 미확인 항목이면 브라우저 확인을 완료한 것으로 읽지 않습니다.
4. `luna-desktop.png`, `mobile.png`: 사분면·종합표와 좁은 화면 확인 이미지입니다.
5. `documentation-validation.json`: 공통 문서 연결·해시 검사입니다. 최신 PASS/FAIL과 오류 목록은 이 파일의 결과를 따릅니다. 시안의 데이터·브라우저 확인 결과와 구별합니다.
6. `density-before.json`, `density-verification.json`, `density-static-verification.json`: 공간 축소 전후의 같은 화면 너비에서 비교표·사분면 크기를 측정한 기록과 9단계 배경 확인입니다. 화면의 숫자·모델 전환·모바일 배치도 함께 확인합니다. 변경 후 화면은 `luna-desktop-compact.png`, `mobile-compact.png`에 저장합니다.
7. `dataset-unit-tests.log`, `dataset-verification.json`: 데이터셋별 취합의 회귀 검사, 데이터셋·문항 묶음·모델 전환과 반응형 확인입니다. 화면은 `dataset-tatqa-desktop.png`, `dataset-finance-desktop.png`, `dataset-mobile.png`입니다.
8. `model-order-verification.json`: Luna → Haiku 4.5 → Qwen3 14B → Qwen3 8B 순서의 버튼·비교표·범례 확인입니다. 집계 없는 모델 버튼도 같은 순서에 놓습니다.
9. `seven-feature-static-verification.json`, `seven-feature-unit-tests.log`: 7조건 × 모델 × 네 조합의 저장 집계 일치와 분모·EA 범주 회귀 검사입니다.
10. `two-screen-verification.json`: 두 화면의 독립 전환, 1/2화면 전환, 선택 복원, 조건별 합계·숫자 표시, 모델 순서와 반응형 확인입니다. `two-screen-desktop.png`와 `two-screen-mobile.png`는 이 변경의 화면 기록입니다.
11. `model-quadrant-verification.json`: 모델 체크·상하 선택 연결·분면 위치와 폭 일치·건수/증감·좁은 칸의 비율/기준 숨김·기호 행과 하단 범례·새로 고침 복원 확인입니다. `model-quadrant-desktop.png`, `model-quadrant-compact.png`, `model-quadrant-mobile.png`, `model-quadrant-wide.png`는 해당 화면 기록입니다. 기존 비교표에 대한 과거 확인 기록과 현재 모델별 사분면 확인은 구별합니다.

[독립 HTML](../../../outputs/research/20260930-ic-value-quadrant/ic-value-quadrant.html)과 [파일 역할·생성 흐름](../../../outputs/research/20260930-ic-value-quadrant/README.md)을 함께 봅니다. 원자료는 `reports/experiments-run`에 보존합니다. 기존 viewer/experiments 코드는 이 시안의 변경 대상이 아닙니다.

핵심 확인값은 Luna Unguided/ON에서 B +25건·null +10건, Haiku Guided/OFF에서 형식·실행 실패 +50건입니다. 증가 배경을 개선 점수로 읽지 않도록 실패 행과 해석 범위를 보존합니다.

데이터셋별 취합은 저장 A02가 있는 7개 실행을 2개 데이터셋·3개 입력 묶음으로 나눕니다. TAT-QA 557문항은 3모델이며 Qwen3 14B는 집계 없음, FinanceReasoning 1,080문항은 3모델이며 10문항 Luna 실행은 별도입니다. 출력 잘림 때문에 `collected`가 작아도 실패 합계와 계획 분모를 유지합니다. 전체 실행의 포함 여부는 독립 HTML과 함께 저장한 `run-inventory.json`을 봅니다. FinanceReasoning의 프롬프트 버전 차이와 원래 `input_path`의 부정확한 데이터셋 표기는 생성 README에 설명합니다.

이 README는 `src/finarch/documentation/templates/research/ic-value-quadrant-log-readme.md`에서 생성합니다. 프로그램·문서·화면 확인과 사용자의 직접 확인은 구별합니다.

7조건 자료는 Python으로 저장 결과를 읽어 HTML 안에 넣습니다. 브라우저의 JavaScript는 두 화면의 선택·증감·표시만 처리합니다. 새 모델 호출·재채점·자동 서버 조회는 하지 않습니다. 각 조건의 실제 문항 수와 실패를 분모에 보존하며 EA에 후보 B를 만들지 않습니다.
