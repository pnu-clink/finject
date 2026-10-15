# 실험 목적 영역 접힘 상태 유지

## 읽는 순서

1. [실험 뷰어](http://127.0.0.1:8894/?run=20260923-exp-008&tab=overview)의 **이 실험은 무엇을 확인하나요?**를 접습니다. 필터 변경·탭 왕복·새로 읽기·브라우저 새로고침 후 같은 상태인지 확인합니다.
2. [확인 기록](checks.json)에서 실제로 확인한 동작과 범위를 읽습니다.
3. [파일 책임·흐름도](../../docs/02-experiments/README.md)를 읽습니다.

## 파일 역할

|파일|역할|
|---|---|
|[app.js](../../viewer/experiments/app.js)|목적 영역의 고정 키, 선택 상태 저장·복원, 갱신 중 변경 보존|
|[checks.json](checks.json)|원래 현상과 수정 후 실제 브라우저 확인 결과|
|[문서 갱신 로그](documentation-refresh.log)|중앙 템플릿에서 README와 문서 색인을 생성한 기록|
|[문서 검증 로그](documentation-validate.log)|현재 문서 연결·보관 원본 해시 검사 결과|

저장한 선택이 없을 때만 기본으로 펼칩니다. 같은 브라우저·같은 뷰어 주소에서는 실행이 달라도 마지막 선택을 사용합니다. 저장소가 차단된 환경에서는 현재 페이지 안에서만 유지합니다. 이후 생성하는 HTML Export에도 같은 화면 코드가 포함되며 기존에 내려받은 사본은 바뀌지 않습니다.

실험 입력·원응답을 변경하거나 모델을 호출하는 작업이 아닙니다. 에이전트의 확인은 사용자 검토 완료를 의미하지 않습니다.

이 README는 `src/finarch/documentation/templates/viewer-experiments-disclosure-state.md`에서 생성합니다. 다시 생성하려면 `python3 src/finarch/documentation/manage.py refresh`를 실행합니다.
