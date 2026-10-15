# 실험 뷰어 — 키보드 이동·조합 선택

이 문서는 당시 W/S의 문항번호·Q/C 위치 이동을 확인한 기록입니다. 현재 W/S는 모든 화면에서 반 화면씩 위/아래로 스크롤합니다. [현행 동작 확인](../viewer-experiments-scroll-shortcut/README.md)을 먼저 확인해 주세요.

## 읽는 순서

1. [문항 비교](http://127.0.0.1:8894/?run=20260923-exp-007&tab=case&case=test-0006&variant=IC_VALUE_01_AFTER)에서 **키보드 단축키**를 펼칩니다. 데이터셋 뷰어와 같은 키보드 배열로 문항은 파랑, 유형은 주황, 조건은 보라, 화면·본문 위치는 초록으로 표시합니다.
2. **Q/E**로 이전/다음 문항, **A/D 또는 B**로 원본부터 EA-02까지 유형을 이동합니다. 이 기록 작성 당시 **W/S**는 문항번호/Q·C 위치였으며, **1–6**은 전체 결과부터 보고서·이력까지 상단 화면입니다. 문항 이동은 현재 필터 범위에서 25개 목록 페이지를 이어 이동하며 양 끝에서 멈춥니다.
3. 조건 줄 앞에 **(Unguided Solving, 끔), (Unguided Solving, 켬), (Criteria-Guided Solving, 끔), (Criteria-Guided Solving, 켬)**이 있습니다. **Z/C로 이 네 조합에 도착하면 즉시 선택**됩니다. 뒤쪽 Unguided Solving/Criteria-Guided Solving·Reasoning OFF/Reasoning ON 버튼은 Z/C로 초점을 옮긴 후 **Space/Enter**로 선택합니다. Tab/Shift+Tab도 사용합니다. 앞/뒤 선택 표시는 서로 동기화되며 선택색의 브라운 농도와 초점 테두리를 구분합니다.
4. 각 조합 아래에서 해당 문항·유형·모델의 **저장된 최종 시도 시간**을 읽습니다. 여러 모델은 각각 표시하며 시간 미기록·읽기 오류·요청 없음과 실제 0초를 구분합니다. 원본의 Criteria-Guided Solving은 계획되지 않아 선택할 수 없습니다.
5. [확인 기록](checks.json), [검사 로그](tests.log), [동작·파일별 책임·순서도](../../docs/02-experiments/README.md)를 봅니다.

입력란·선택 상자 사용 중 또는 팝업이 열린 동안 이동 단축키는 작동하지 않습니다. Ctrl/Alt/Meta 조합·한글 조합 입력·키 반복도 제외합니다. 1 전체 결과는 클릭과 같이 조회 필터를 초기화합니다. 이후 만드는 단일 HTML Export에도 동일한 기능을 포함합니다.

## 파일 역할

|파일|역할|
|---|---|
|[model.mjs](../../viewer/experiments/model.mjs)|필터 후 전체 문항의 이웃·페이지, 4개 조합, 시간 값과 누락 상태|
|[repository.mjs](../../src/finarch/experiments/viewer/repository.mjs)|저장 result/call의 시간 읽기. 다른 조합의 손상 파일을 현재 응답 조회와 분리|
|[app.js](../../viewer/experiments/app.js)|단축키·입력 보호, 버튼 동기화·시간 표시·화면 갱신 후 초점 복원|
|[index.html](../../viewer/experiments/index.html) / [styles.css](../../viewer/experiments/styles.css)|키보드 모양, 기능별 안내색, 조합/개별 선택색·초점 테두리|
|[offline.mjs](../../viewer/experiments/offline.mjs)|단일 HTML에서도 같은 문항·조합·시간 선택|
|[checks.json](checks.json)|실제 브라우저 확인·회귀 검사 결과·변경 파일 해시|
|[tests.log](tests.log)|문항 페이지·필터 이동, 시간 누락/오류/0초, 오프라인 자료 일치와 기존 뷰어 회귀 검사|
|[tests-sandbox.log](tests-sandbox.log)|최초 39개 검사 중 HTTP 2개가 localhost 권한 제한으로 중단된 기록. 이후 검사를 추가한 최종 결과는 tests.log|
|[server.log](server.log)|변경한 뷰어 서버의 읽기 로그|
|[documentation-refresh.log](documentation-refresh.log) / [documentation-validate.log](documentation-validate.log)|중앙 템플릿 생성과 문서 연결·보관 원본 해시 검사|

처리 시간은 재시도 합계·화면 로딩 시간이 아닙니다. `result.elapsed_seconds`를 먼저 읽고 없으면 `call.result.elapsed_seconds`를 확인합니다. 저장 결과와 원응답을 바꾸거나 모델을 추가 호출하지 않습니다. 브라우저 확인은 에이전트의 확인이며 사용자 검토 완료를 뜻하지 않습니다.

이 README는 `src/finarch/documentation/templates/viewer-experiments-keyboard.md`에서 `python3 src/finarch/documentation/manage.py refresh`로 생성합니다.
