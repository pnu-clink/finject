# EA 유형 라벨 통일

상태: {status}

|기존 식별자|현재 식별자|의미|
|---|---|---|
|EA_02 / EA-02|EA_01 / EA-01|앞쪽 입력 삭제|
|EA_03 / EA-03|EA_02 / EA-02|뒤쪽 입력 삭제|

한 번의 동시 매핑으로 변경합니다. 이미 정상인 `EA 01 / EA 02` 표시와 `06-ea-earlier-input / 07-ea-later-input` 저장 폴더는 유지합니다. 계산·문장·판정·비용을 다시 생성하거나 LLM을 호출하지 않습니다.

## 읽는 순서

1. `completed.json`, `final-integrity.json`: 최종 파일 대조와 완료 결과. `status`가 VERIFIED/COMPLETE인지 확인합니다.
2. `changes.jsonl`: 완료 시 내보내는 파일별 원본 위치와 변경 전후 SHA256. 진행 중 원장은 `finish.sqlite`입니다.
3. `finish-labels.log` → `finish-readmes.log` → `finish-hashes.log`: 단계별 진행 내역. 의도적으로 중단하고 이어 실행한 기록도 보존합니다.
4. `recovery-tests.log`, `regression.log`, `viewer-tests.log`, `syntax-check.log`: 로컬 검사 결과. 최종 결과는 아래 상태와 함께 확인합니다.
5. `originals-recovered.zip`, `additional-originals/`: 정상 복구한 기존 백업과 추가 원본. 중단 당시의 `originals.zip`도 그대로 보존합니다.
6. `interruption-check.json`, `staged-audit-summary.json`: 중단 원인 점검과 최초 분할 검사 결과이며, 최종 완료 결과와 구분합니다.
7. `summary-label-check.json`, `workbook-validation.json`: 주요 실행 집계 대조와 엑셀 14개 검사. 요약 JSON의 카운트는 중첩 기록의 필드 등장 횟수이며 문항 수가 아닙니다.
8. `concurrent-changes.json`: 최종 대조 중 발견한 다른 작업의 변경·폴더 이동 7건과 검증 근거. 이 변경을 덮어쓰지 않았습니다.
9. `viewer-verification.json`, `viewer-label-mapping.log`: 실제 공통 뷰어와 EA 저장 경로 연결 확인.
10. `delegated-originals.json`, `delegated-originals.zip`: 실험 폴더 담당 작업에 전달한 변경 전 원본 2,177개. 실험 폴더 이동과 라벨 이행은 해당 작업에서 별도 검증합니다.

Git 이력·archive·의존성·별도 worktree는 보존합니다. `reports/feedback-011-017`의 이미 정상인 유형 분류도 유지하며, 내부 원기록의 이전 label만 매핑합니다. 백업 복원 시 다른 작업의 후속 변경 및 이동된 경로를 먼저 확인해야 합니다.

공통 뷰어: [FinanceReasoning](http://127.0.0.1:8893/dataset/?run=20260917-002), [TAT-QA](http://127.0.0.1:8893/dataset/?run=20260917-003). 서버 실행 시 저장된 최신 자료를 읽습니다. 별도 뷰어 HTML은 생성하지 않습니다.

{details}

안전장치와 책임 순서도: [EA 라벨과 중단 복구](../../docs/77-ea-label-migration.md).
