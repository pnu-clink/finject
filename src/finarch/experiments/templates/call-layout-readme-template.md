# {run_id} 호출 폴더 정리

검증 상태: **{status}** · 확인 시각: {verified_at}

해시로만 구분했던 호출을 모델별 `calls/<문항>/<유형>/<문항>-P0-R-off.json`에서 읽을 수 있습니다. 원본은 두 조건, 변형은 P0/P1 × R-off/R-on 네 조건입니다. EA는 실제 데이터 ID에 맞춰 06-EA-01, 07-EA-02입니다.

## 읽는 순서

1. [검증 결과](verification.json): 읽기용 JSON {readable_call_files}개, 이동한 호출 폴더 {moved_trial_folders}개, 원기록 파일 {preserved_files}개의 해시 확인.
2. [경로 대응표](mapping.jsonl): 이전 해시 경로 → 현재 원기록 경로 → 읽기용 JSON.
3. [원기록 해시](record-hashes.jsonl): 이전·현재 파일 경로와 이동 전 SHA-256. 이동 후 같은 해시임을 검사했습니다.
4. [이동 계획](plan.json): 유형 대응 확인과 이동 전 요청 수·상태·사용량·비용.
5. `before/`: 정리 전 보고서·집계·분석 사본. 이력 보존본이므로 당시 경로가 그대로 남습니다. 현재 결과는 실행 폴더의 REPORT.md와 calls에서 읽고 옛 경로는 mapping.jsonl로 찾습니다.
6. [실행 로그](../events.jsonl): CALL_LAYOUT_STARTED와 CALL_LAYOUT_VERIFIED 기록.

실제 모델 호출은 {new_model_calls}건입니다. 폴더 이동 중 요청·스키마·정답·원응답은 변경하지 않았고, 요청 수·상태·사용 토큰·추정 비용을 이동 전과 대조했습니다. `_records`의 원기록만 비용·재개 판단에 사용하며 읽기용 JSON을 별도 호출로 세지 않습니다. 시도하지 않은 요청에는 호출 파일을 생성하지 않습니다.

프로젝트 전체의 EA 번호 변경을 함께 반영한 실행에는 별도로 `label-migration/` 기록이 있습니다. EA_02/EA_03을 EA_01/EA_02로 정리한 메타데이터 변경 전 원본·이전 manifest는 그 폴더에 보존합니다. 폴더 이동의 해시 기준은 해당 메타데이터 정리 이후입니다.

이 문서는 `src/finarch/experiments/templates/call-layout-readme-template.md`에서 자동 생성했습니다. 화면 구현과 HTML 생성은 이번 작업 범위에 포함되지 않습니다.
