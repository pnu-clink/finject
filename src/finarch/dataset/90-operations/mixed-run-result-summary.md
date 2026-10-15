
## 이번 실행의 완료 결과

Preparation: {preparation_pass}/{input_count}건 통과, {preparation_fail}건 미통과. Generation은 통과한 {generation_cases}문항 × 7유형 = {generation_total}건을 최대 3차까지 처리해 {generation_pass}건 통과, {generation_fail}건 실패, {generation_unevaluated}건 미평가입니다. 7유형 모두 자동 검사에 통과한 문항은 {all_types_pass}건입니다. 자동 통과는 사람 승인이나 의미 정답의 보장이 아닙니다.

| 입력 구분 | 선별 | Preparation 통과 | 미통과 |
|---|---:|---:|---:|
{source_rows}

| Generation 유형 | 대상 | 최종 통과 | 실패 | 미평가 |
|---|---:|---:|---:|---:|
{type_rows}

results는 전체 선별 문항의 상태를 보존하는 검토용 취합본입니다. 각 유형 파일의 Preparation 미통과 {preparation_fail}문항은 `NOT_RUN`으로 남아 있으며, 실제 생성·통과 문항으로 세면 안 됩니다. 명시적인 사람 Reject만 Export에서 제외하는 현재 정책을 적용했습니다.

- [최종 취합본 읽는 순서](results/README.md) → [파일 수량·해시·제외 목록](results/manifest.json).
- [Preparation Excel](phase-reports/preparation/preparation-report.xlsx), [Generation Excel](phase-reports/generation/generation-report.xlsx).
- [완료 확인 기록](completion-audit.json), [마지막 집계 연결 오류와 복구 기록](completion-recovery.json). 제작·유료 호출은 재실행하지 않았습니다.
- [API 사용량](api-usage/README.md): {api_calls}호출, 기록 확인분 비용 약 ${estimated_cost}. 사용량·비용 미확인 {missing_cost_calls}호출은 별도이며 실제 청구액이 아닙니다.

현재 새 호출의 제한은 300초입니다. 일시적으로 900초를 적용했던 변경과 사용자 지시에 따른 원복 내역은 [원복 기록](runtime-adjustments/001-api-wait/README.md)에 보존했습니다. 이번 제작에 대상 모델 Evaluation/Analysis나 별도 실패 해석 호출은 없습니다.

EA 역산 참고 표식의 최신 저장 기록은 완료 {inverse_completed}건, 호출 실패 {inverse_failed}건입니다. 호출 실패의 가능 여부는 미확인으로 남겼으며, 역산 가능 여부나 이 참고 검사의 실패가 자동 품질 판정을 바꾸지는 않습니다. 상세 상태는 completion-audit.json과 각 inverse-review.json에서 확인합니다.
