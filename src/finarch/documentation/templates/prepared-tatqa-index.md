# TAT-QA 데이터 준비·결과 전달

## 현재 우선 실험의 결과 세트

[20261003-003 전달본](20261003-003/README.md)은 [20261003-003 · TAT-QA Generation](../../../reports/run/20261003-003/README.md)의 취합 결과를 보존한 실험용 데이터 폴더입니다. 원본 437건의 결과·실패 기록을 보존하며 원본과 7변형이 모두 자동 PASS인 291문항군을 새 Evaluation 대상으로 선정합니다.

- 전달 데이터: `data/prepared/tatqa/20261003-003/00-input.json`과 `01`~`07` 유형 JSON.
- 원천 해시·선정 범위: [prepared-results.json](20261003-003/prepared-results.json), [manifest.json](20261003-003/manifest.json).
- 제작 과정·원응답·사람 판정: 원래 `reports/run/20261003-003`에 보존.
- 전달·입력 동일성 검사: [작업 기록](../../../log/tatqa-prepared-20261003/README.md).
- Evaluation 요청·원응답·상태: 별도 `reports/experiments-run`에 저장하고 [공통 실험 뷰어](http://127.0.0.1:8894/)에서 확인.

## 기존 원천 입력

[full-20260917](full-20260917/README.md)은 원천에서 준비한 원본 입력입니다. 새 Generation 결과 전달본이나 이번 291문항군의 실험 결과와 구별합니다.

이 README는 `src/finarch/documentation/templates/prepared-tatqa-index.md`에서 생성합니다.
