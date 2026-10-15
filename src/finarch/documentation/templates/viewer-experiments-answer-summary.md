# 실험 뷰어 — 간결한 답변·숫자 비교·잘림 사유

## 읽는 순서

1. [숫자 일치 예시](http://127.0.0.1:8894/?run=20260923-exp-007&tab=case&case=test-0006&variant=ORIGINAL&prompt=P0&reasoning=off)를 봅니다. `모델이 반환한 답 (FinancialAnswerV6 · negative=false · scale=million)` 다음에 답 **20**, 같은 상자 아래에 **저장된 숫자 비교: 20 ↔ 20 · 일치**가 표시됩니다. 숫자 일치는 갈색 상자이며 부호·scale 처리 방식의 반복 안내는 제거했습니다.
2. [숫자 불일치 예시](http://127.0.0.1:8894/?run=20260923-exp-007&tab=case&case=test-0052&variant=ORIGINAL&prompt=P0&reasoning=on)는 **0.5 ↔ 12.1 · 불일치**입니다. 답변 배경을 밝게 하고 EXPLANATION에 연한 황금색 배경과 강조선을 넣었습니다. 미평가도 밝은 배경을 사용하되 실제 미평가 문구를 유지합니다.
3. [출력 잘림 예시](http://127.0.0.1:8894/?run=20260923-exp-007&tab=case&case=test-0168&variant=IC_VALUE_01_AFTER&prompt=P1&reasoning=off)에는 진한 빨강 **출력 잘림** 배지와 **출력 토큰 한도** 사유가 나란히 있습니다. 완성된 답 표시값은 **Null**이며 수신한 잘린 원문은 기존 JSON 뷰어에서 확인합니다.
4. [확인 기록](checks.json), [검사 로그](tests.log), [현재 동작·파일별 책임·순서도](../../docs/02-experiments/README.md)를 확인합니다.

갈색은 저장된 숫자 비교의 일치 표시이며 의미 정답 판정이 아닙니다. Null은 화면 표시값입니다. 실제 반환 null, answer 필드 없음, 완성된 응답 본문 없음은 툴팁·접근성 설명·원기록으로 구분합니다. 실제 숫자 0은 0으로 표시하고, 저장 원응답이나 판정을 바꾸지 않습니다. 출력 토큰 한도 문구는 저장 진단 `OUTPUT_TRUNCATED` 또는 종료 사유 `max_tokens`가 있는 출력 잘림 응답에만 표시합니다.

## 파일 역할

|파일|역할|
|---|---|
|[app.js](../../viewer/experiments/app.js)|메타정보를 제목 줄에 배치, 숫자 비교를 답변 상자에 통합, Null 표시, 설명 강조 분기, 잘림 사유 연결|
|[styles.css](../../viewer/experiments/styles.css)|줄 수·크기·여백 축소, 숫자 일치 갈색, 밝은 답변과 설명 강조, 진한 빨강 잘림 배지|
|[checks.json](checks.json)|저장 근거와 브라우저의 일치·불일치·잘림·실제 null·실제 0 확인, 파일 해시|
|[tests.log](tests.log)|기존 HTML Export 검사로 최신 화면 코드의 문법·포함과 CSP 해시 확인|
|[documentation-refresh.log](documentation-refresh.log) / [documentation-validate.log](documentation-validate.log)|중앙 템플릿 생성과 문서 연결·보관 원본 해시 검사|

이후 생성하는 HTML Export에도 동일한 코드·스타일을 포함합니다. 모델 호출·실험 재실행은 없으며 에이전트의 확인을 사용자 검토 완료로 표시하지 않습니다.

이 README는 `src/finarch/documentation/templates/viewer-experiments-answer-summary.md`에서 `python3 src/finarch/documentation/manage.py refresh`로 생성합니다.
