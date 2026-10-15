# 실험 JSON 뷰어·팝업 닫기

## 읽는 순서

1. [문항 비교](http://127.0.0.1:8894/?run=20260923-exp-007&tab=case&case=test-0006)에서 **모델에 전달한 입력 → JSON schema**를 펼칩니다.
2. JSON 뷰어의 삼각형으로 객체·배열을 접거나 펼칩니다. **전체 펼치기 / 전체 접기 / 원문 보기 / 원본 복사**를 사용할 수 있습니다.
3. 응답 카드의 **정확한 요청 / 응답 JSON / 검사·진단**과 원기록 파일에서도 같은 뷰어를 사용합니다. 비용·실행의 상태·사용량·이벤트도 같습니다.
4. [확인 기록](checks.json)과 [검사 로그](tests.log)에서 실제 화면 확인과 자동 검사 결과를 봅니다. 파일 책임·흐름은 [운영 문서](../../docs/02-experiments/README.md)에 있습니다.

저장 기록과 HTML Export 팝업은 **창 바깥 클릭**, Esc 또는 닫기 버튼으로 닫습니다. 내부 클릭과 내부에서 시작한 드래그는 닫기 동작이 아닙니다. 내보내기 중 Export 창을 닫으면 해당 요청을 취소합니다.

## 파일 역할

|파일|역할|
|---|---|
|[json-viewer.mjs](../../viewer/experiments/json-viewer.mjs)|JSON/JSONL 문법 검사, 원문 토큰 트리, 200줄 페이지, 접기·펼치기·복사|
|[app.js](../../viewer/experiments/app.js)|schema·요청·응답·검사·원기록·문서·이벤트를 공통 뷰어로 연결|
|[styles.css](../../viewer/experiments/styles.css)|브라운 테마, 값 종류별 색상, 키보드 포커스|
|[server.mjs](../../src/finarch/experiments/viewer/server.mjs)|허용된 JSON 뷰어 정적 모듈 제공|
|[export-html.mjs](../../src/finarch/experiments/viewer/export-html.mjs)|같은 JSON 뷰어와 CSS를 단일 HTML에 포함|
|[checks.json](checks.json)|실제 문항의 브라우저 확인, 자동 검사 결과, 변경 파일 해시|
|[tests.log](tests.log)|뷰어·저장 자료·HTML 내보내기 회귀 검사|
|[tests-sandbox.log](tests-sandbox.log)|첫 실행에서 localhost HTTP 검사 2개가 권한 제한으로 막힌 기록. 재실행 결과는 tests.log 참고|
|[server.log](server.log)|JSON 모듈을 포함해 갱신한 로컬 뷰어 서버의 읽기 로그|
|[token-limit-review.json](token-limit-review.json)|사용자의 상한 질문에 답하기 위해 exp-007의 저장된 3,000결과에서 확인한 출력 토큰 분포·잘림 1건의 원기록 위치. 설정 변경·재호출 없음|
|[documentation-refresh.log](documentation-refresh.log) / [documentation-validate.log](documentation-validate.log)|중앙 템플릿 생성·문서 연결·보관 원본 해시 검사|

원기록 파일의 큰 정수, 중복 키, 이스케이프와 숫자 표기를 다시 만들지 않습니다. API에서 이미 객체로 받은 값은 JSON으로 표시하며, 원래 파일의 공백까지 비교하려면 연결된 원기록을 엽니다. JSONL은 원래 행 번호를 표시합니다. 불완전한 JSON은 오류 안내와 원문을 그대로 남깁니다. 큰 트리는 다음/이전 200줄로 끝까지 확인할 수 있습니다.

prompt·Q/C의 일반 문장과 근거 강조, 영역별 접힘 상태 저장은 유지합니다. 이후 생성하는 HTML Export에도 같은 JSON 뷰어가 들어가며 기존 사본을 덮어쓰지 않습니다. 저장 실험 결과를 수정하거나 모델을 추가 호출하지 않습니다. 에이전트의 확인을 사용자 검토 완료로 표시하지 않습니다.

이 README는 `src/finarch/documentation/templates/viewer-experiments-json-viewer.md`에서 `python3 src/finarch/documentation/manage.py refresh`로 생성합니다.
