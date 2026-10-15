# 응답 근거 검토 표시 계약과 문서 링크 수정 · 2026-10-03

[뷰어 입력 계약](../../docs/02-experiments/02_analysis/02_comparison/03-viewer-grounding-contract.md) · [검토 설계](../../docs/02-experiments/02_analysis/02_comparison/02-response-grounding-review.md) · [실험 뷰어](../../viewer/experiments/README.md)

## 읽는 순서

1. 위 입력 계약에서 현재 구현·추가 저장 요구·분모·원문 연결·A03 책임 경계를 확인합니다.
2. [verification.json](verification.json)에서 이번 수정과 실제 검사 범위를 읽습니다.
3. [controller-tests.log](controller-tests.log)와 [regression-tests.log](regression-tests.log)는 로컬 제어 흐름·기존 서버 검사의 실제 출력입니다.
4. [api-verification.json](api-verification.json)·[browser-verification.json](browser-verification.json)은 등록 문서 해시·목록 정책과 실제 화면 확인 결과입니다. [문서 화면](documentation.png).
5. [source-baseline.json](source-baseline.json)·[source-preservation.json](source-preservation.json)은 수정 범위와 실험 입력·집계·원응답의 보존 확인입니다.

## 완료·대기 경계

- 응답별 판정의 뷰어 입력 계약을 검토했습니다. 새 판정·집계·schema·LLM 실행은 없습니다. 새 판정 표시 기능은 실제 계약과 저장 파일 제공 전입니다.
- 명시적인 `run/doc` 링크가 데이터셋 목록의 최신 실행으로 대체되던 문제를 `viewer/dataset/shell.html`에서 수정했습니다. 문서 전용 run을 데이터셋 선택 목록에 추가하지 않았습니다.
- 기존 `reports/documentation.js`·Python 문서 조회를 사용하며, 공통 `viewer/dataset/index.html`을 소스에서 재조립했습니다.
- 모델 호출·실험 재실행·중지된 Analysis 재개·기존 판정 수정은 하지 않았습니다.

문서는 `src/finarch/documentation/templates/viewer-response-grounding-contract.md`에서 생성합니다. 문서 갱신·검사 기록은 [documentation-refresh.json](documentation-refresh.json)·[documentation-validation.json](documentation-validation.json)에 있습니다. 로컬 검사 통과·브라우저 표시 확인과 사용자의 연구 판단은 별개입니다.
