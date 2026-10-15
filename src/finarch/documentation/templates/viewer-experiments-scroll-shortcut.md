# 실험 뷰어 — W/S 반 화면 스크롤

[실험 뷰어 사용법](../../viewer/experiments/README.md) · [동작·파일별 흐름](../../docs/02-experiments/README.md)

## 확인 순서

1. [문항 비교](http://127.0.0.1:8894/?run=20260923-exp-008&tab=case&case=test-0006)에서 **키보드 단축키**를 펼쳐 W/S 키 설명을 확인합니다.
2. 입력란과 팝업에서 벗어난 상태로 **S**를 누르면 아래로, **W**를 누르면 위로 현재 화면 높이의 절반만큼 이동합니다. 실패 분석 등 다른 화면에서도 같습니다.
3. [실제 화면 확인](checks.json), [자동 검사](tests.log), [문서 갱신](documentation-refresh.log), [문서 검증](documentation-validate.log)을 읽습니다.

## 변경과 범위

이전 W/S는 문항 비교에서 문항 제목과 Q/C로 바로 이동하며 S가 입력 영역을 펼쳤습니다. 현재 W/S는 위치만 이동합니다. 접힌 항목·문항·유형·필터·URL은 바꾸지 않습니다. 입력란·선택 상자 사용 중이나 팝업이 열려 있을 때, 조합 키·키 반복 입력에는 기존 보호 조건을 적용합니다. 모든 화면과 새로 내보내는 단일 HTML에 같은 `app.js`와 `index.html`이 들어갑니다.

|파일|역할|
|---|---|
|[app.js](../../viewer/experiments/app.js)|키 입력 검사 후 화면 높이 절반만큼 `scrollBy` 호출|
|[index.html](../../viewer/experiments/index.html)|키보드 모양과 W/S 설명|
|[viewer-experiments.md](../../src/finarch/documentation/templates/viewer-experiments.md)|사용법 README의 중앙 원본|
|[experiments-operations.md](../../src/finarch/documentation/templates/experiments.md)|운영 안내 README의 중앙 원본|
|[checks.json](checks.json)|실제 브라우저 이동 거리·입력 보호·원상태 보존|
|[tests.log](tests.log)|실험 뷰어 전체 회귀 검사|

이 로그는 화면 코드와 문서 변경 확인입니다. 저장된 실험 결과나 모델 응답을 변경한 기록은 아닙니다. 브라우저 검증과 사용자 검토 완료도 구분합니다.

이 README는 `src/finarch/documentation/templates/viewer-experiments-scroll-shortcut.md`에서 `python3 src/finarch/documentation/manage.py refresh`로 생성합니다.
