# 실험 뷰어 — 모델 답변을 먼저 읽는 배치

## 읽는 순서

1. [문항 비교](http://127.0.0.1:8894/?run=20260923-exp-007&tab=case&case=test-0006&variant=IC_VALUE_01_AFTER&prompt=P0)에서 문항·유형·조건을 선택합니다.
2. 맨 위 **모델별 답변**에서 모델명·반환 답·설명·근거를 읽습니다. 답·계약정보·숫자 비교는 한 상자에 있으며 숫자 일치는 갈색, 그 외에는 밝은 배경과 설명 강조로 구분합니다. 검사 상태·오류·원응답·시도 이력도 같은 카드에서 확인합니다.
3. 그 아래 **실험 원본 ↔ 현재 입력 · 문자열 차이 보기**를 펼칩니다. 입력 패널과 별도 영역이며 좌우의 삭제/추가 문자열을 비교합니다. 비교할 실험 원본이 있는 변형에만 표시합니다. 접기·펼치기 선택은 저장합니다.
4. 맨 아래 **모델에 전달한 입력**에서 prompt → JSON schema → 추가 입력 → 요청 설정 → Q/C 순서로 확인합니다. 답변 카드의 근거를 누르면 이 영역과 Q/C가 펼쳐지고 정확 문자열 위치로 이동합니다.
5. [최초 배치 확인 기록](checks.json), [당시 HTML Export 검사 로그](tests.log), [후속 답변 간소화·진단 표시](../viewer-experiments-answer-summary/README.md), [동작·책임·순서도](../../docs/02-experiments/README.md)를 확인합니다.

원본 유형은 비교할 별도 변형이 없으므로 모델별 답변 다음에 입력을 표시합니다. 강조는 읽기 편의를 위한 것으로 모델 답의 정답 판정이 아닙니다. 저장 응답·원점수·모델 입력은 수정하지 않습니다. 이후 생성하는 HTML Export에도 같은 화면 코드와 스타일을 포함합니다.

## 파일 역할

|파일|역할|
|---|---|
|[app.js](../../viewer/experiments/app.js)|모델 답변을 위로, 차이를 별도 영역으로, 실제 입력을 아래로 배치. 근거 클릭과 접힘 상태 유지|
|[styles.css](../../viewer/experiments/styles.css)|반환 답·숫자 비교 상태에 따른 배경·모델명/설명 강조·차이 보기 구분|
|[checks.json](checks.json)|원본/변형 배치·근거 강조·조건 선택·브라우저 표시와 파일 해시 확인|
|[tests.log](tests.log)|기존 단일 HTML 검사로 최신 화면 코드의 문법·포함 여부·CSP 해시 확인|
|[documentation-refresh.log](documentation-refresh.log) / [documentation-validate.log](documentation-validate.log)|중앙 템플릿 생성과 문서 연결·보관 원본 해시 검사|

이번 변경은 표시 순서와 강조를 바꾸는 작업입니다. 실제 모델 호출·실험 재실행은 없으며 브라우저의 에이전트 확인을 사용자 검토 완료로 표시하지 않습니다.

이 README는 `src/finarch/documentation/templates/viewer-experiments-response-layout.md`에서 `python3 src/finarch/documentation/manage.py refresh`로 생성합니다.
