# 실험 뷰어 — 실패 분석 정렬·필터·자동 브라우저 열기

## 확인 순서

1. [실험 뷰어 실행 안내](../../viewer/experiments/README.md)의 `start.command`를 실행합니다. 서버 준비 후 브라우저가 열립니다.
2. 20260923-exp-007을 선택해 **04 실패 분석**을 엽니다. 반환 상태를 **상태 전체**로 바꾸면 3,000요청·100문항을 확인할 수 있습니다.
3. 위쪽 진단 사유 버튼을 고르고 아래 응답 목록을 확인합니다. 문항·유형·모델·프롬프트·추론·반환 상태·진단 사유 열 제목을 눌러 정렬을 바꿉니다.
4. [checks.json](checks.json)에서 실제 확인 항목을, [tests.log](tests.log)에서 52개 자동 검사 결과를, [server.log](server.log)에서 서버 준비·브라우저 열기와 화면 요청을 확인합니다.
5. [문서 갱신 로그](documentation-refresh.log)와 [문서 검증 로그](documentation-validate.log), [상세 책임·흐름](../../docs/02-experiments/README.md)을 읽습니다.

## 화면 변경

- 왼쪽 진단 목록을 본문 위의 가로 버튼으로 옮겼습니다. 선택은 체크 표시·브라운 배경으로 표시하며 다시 클릭하거나 진단 선택 해제로 해제합니다.
- 사유는 건수 많은 순/이름순으로 정렬합니다. 버튼별 건수는 사유 선택 전의 기본 조건 기준이며 실제 결과 수는 아래에 따로 표시합니다.
- 응답은 문항 번호 오름차순이 기본입니다. 숫자가 포함된 ID를 자연스럽게 정렬하고, 전체 응답 정렬 후 30건씩 나눕니다. 같은 값은 고정 보조 순서로 유지합니다.
- 열 제목과 응답 정렬 선택 상자는 같은 상태를 표시합니다. 정렬·사유 변경 시 첫 페이지로 돌아갑니다. 빈 결과에는 필터 해제 안내가 나옵니다.
- `start.command`는 준비된 서버의 주소를 기본 브라우저에 엽니다. 같은 포트·같은 결과 폴더의 뷰어는 재사용하고, 다른 서비스/결과 폴더는 오류로 남깁니다. 브라우저 실행 실패가 서버 종료로 이어지지 않습니다.

## 파일 역할

|파일|역할|
|---|---|
|`viewer/experiments/model.mjs`|숫자를 구분하는 정렬·고정 보조 순서·페이지 범위 보정·사유별 기준 건수|
|`viewer/experiments/app.js`, `styles.css`|상단 진단 필터·건수/선택 표시·응답 열과 정렬 방향·질문 미리보기|
|`viewer/experiments/start.command`, `server.mjs`|서버 준비 후 열기·같은 서버 확인·재실행 처리|
|`src/finarch/experiments/viewer/export-html.mjs`|정렬 상태를 포함하고 같은 app/model/CSS를 단일 HTML에 묶기|
|`tests/failure-sorting.test.mjs`, `tests/launcher.test.mjs`|페이지를 넘는 자연 정렬·중복 사유·필터·서버 준비/재사용/오류 검사|
|`src/finarch/documentation/templates/viewer-experiments.md`|실행·화면 안내 README의 현행 원본|

브라우저에서 exp-007의 정렬·페이지 이동, 진단 선택/해제와 AND/OR 결합, 출력 잘림 우선 표시를 확인합니다. 실제 시작 스크립트로 Chrome이 열린 기록은 server.log와 checks.json에 남깁니다. 기존 43개 회귀 검사와 새 정렬/시작 검사 9개가 포함된 52개가 통과했습니다. 이후 표시 문구 보완은 브라우저에서 확인합니다.

새 HTML Export의 동일 집계·정렬은 자동 대조로 확인합니다. 내보낸 파일의 `file://` 브라우저 실행은 이 작업의 확인 범위가 아닙니다. 새 모델 호출·실험 결과 재계산은 없으며 사용자 검토 완료를 뜻하지 않습니다.

이 README는 `src/finarch/documentation/templates/viewer-experiments-failures.md`에서 생성합니다.
