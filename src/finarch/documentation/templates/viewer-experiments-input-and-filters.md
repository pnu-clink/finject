# 문항 입력 구성·전체 결과 필터 복귀

## 읽는 순서

1. [전체 결과](http://127.0.0.1:8894/?run=20260923-exp-007&tab=overview)에서 원본 숫자 일치 → 진단 사유 선택 → **01 전체 결과** 순서로 확인합니다. 전체 3,000요청·100원문으로 돌아옵니다.
2. [문항 비교](http://127.0.0.1:8894/?run=20260923-exp-007&tab=case&case=test-0006)에서 **prompt → JSON schema → 추가 입력·요청 설정 → Q/C**를 읽습니다. prompt/schema는 기본 접힘, Q/C는 기본 펼침입니다.
3. [확인 기록](checks.json)에서 진단 선택·해제 두 경로와 실제 요청 내용 대조 결과를 봅니다.
4. [운영 문서](../../docs/02-experiments/README.md)에서 요구사항·파일 책임·실제 흐름을 봅니다.

## 파일 역할

|파일|역할|
|---|---|
|[app.js](../../viewer/experiments/app.js)|전체 결과 복귀 시 필터 초기화, 입력 구성, 영역별 접힘 상태 저장|
|[styles.css](../../viewer/experiments/styles.css)|입력 구분선·제목·Q/C 라벨|
|[checks.json](checks.json)|실제 브라우저의 이동·입력 대조·접힘 확인|
|[tests.log](tests.log)|기존 저장 자료·HTML 내보내기 회귀 검사 결과|
|[tests-sandbox.log](tests-sandbox.log)|첫 실행에서 HTTP 검사 2개가 localhost 권한 제한으로 막힌 기록. 허용된 재실행 결과는 tests.log에 보존|
|[documentation-refresh.log](documentation-refresh.log) / [documentation-validate.log](documentation-validate.log)|중앙 템플릿 생성·문서 연결·보관 원본 해시 검사|

**진단 선택 해제**는 진단 사유만 해제합니다. 숫자 일치 등 상위 조건까지 모두 해제하려면 **01 전체 결과** 또는 **필터 초기화**를 사용합니다. 전체 결과에서 직접 필터를 고르는 기능은 유지합니다.

추가 입력의 `answer_format`과 요청의 모델·추론·토큰·캐시 정책·식별 정보를 Q/C 위에 구분합니다. 영문 prompt/schema/Q/C는 저장된 그대로 표시합니다. 분석자 정답은 모델에 보내지 않은 정보로 구분합니다. 사용자가 접거나 펼치면 다음 갱신에도 그 상태를 유지하며, 근거 선택은 Q/C를 펼쳐 강조합니다.

실험 입력·원응답을 수정하거나 모델을 호출하지 않았습니다. 에이전트의 확인은 사용자 검토 완료를 뜻하지 않습니다. 이후 생성하는 HTML Export에도 같은 화면 코드가 들어가며 기존 사본을 덮어쓰지 않습니다.

이 README는 `src/finarch/documentation/templates/viewer-experiments-input-and-filters.md`에서 `python3 src/finarch/documentation/manage.py refresh`로 생성합니다.
