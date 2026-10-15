# Luna API 구현의 오프라인 검사

검사 결과: {status}, {tests}개 검사 통과. 검사 시각: {at}. 이 검사 자체의 모델 호출은 0건입니다.

1. [verification.json](verification.json): 테스트 수·실패 수·검사 당시 구현 해시.
2. [tests.log](tests.log): 캐시 금지 전송 본문, raw 보존, 비용 집계, off/on 사전 확인, 동시 200 한도, 캐시 오류 중단, 불확실 전송 재호출 금지 및 기존 기능 회귀 검사.
3. [hyperparameter-before.json](hyperparameter-before.json): API 전환 전 설정 보존본. 키 값은 포함하지 않습니다.
4. [실제 API 실행 요약](../../experiments-run/20260920-exp-006/RUN-SUMMARY.md) → [3,000원응답 검증](../../experiments-run/20260920-exp-006/api-verification/README.md). 테스트 통과와 실제 API 검증을 구분합니다.

이 README는 `src/finarch/experiments/02-analysis/legacy/comparison/luna-api-check-readme-template.md`에서 생성했습니다. 실제 호출의 코드 해시는 각 요청의 `started.json`에 있습니다. 후속 오프라인 보고서 생성 코드는 원응답을 변경하지 않습니다.
