# {model}

호출 경로: `{transport}` · 계획 {planned}건 · 형식 검사 통과 {valid}건

`cache-preflight.json`이 있으면 먼저 확인합니다. 상태가 `CACHE_POLICY_BLOCKED`일 때는 캐시를 끄는 기능을 확인하지 못해 호출을 시작하지 않은 상태입니다. `cache_verification.status=NOT_CALLED`는 미호출이며 캐시 미사용 실험 완료가 아닙니다.

1. `calls/<문항 ID>/<유형>/<문항 ID>-P0-R-off.json`: 해당 조건의 질문·본문·프롬프트·스키마·응답·검사·사용량을 한 파일에서 확인합니다.
2. 같은 유형 폴더의 다른 JSON: P0/P1(기본/유보 유도)와 R-off/R-on(추론 설정)을 비교합니다. 원본은 P0 두 조건, 변형은 네 조건입니다.
3. `03-results/summary.json`, `results.jsonl`: 조건별 집계와 모든 결과 목록. `call_path`는 읽기용 JSON, `result_path`는 실제 시도 검사 파일입니다.
4. `01-requests/manifest.jsonl`: 실행 당시 고정된 요청과 고유 ID.
5. `calls/<문항 ID>/<유형>/_records/<해시>/attempt-xxx`: 재시도별 요청·원응답·검사 원기록.
6. Codex 실행의 `resources.jsonl`, `resources-latest.json`: 2초 간격 CPU·메모리·동시 한도·진행 중 요청 수. 한도와 실제 진행 중 수는 서로 다릅니다.

유형 순서: `00-Original`, `01-IC-value-before`, `02-IC-value-after`, `03-IC-source-before`, `04-IC-source-after`, `05-IC-relation`, `06-EA-01`, `07-EA-02`입니다. Source before/after는 연결된 value 부모의 위치이며, 원래 유형 ID `IC_SOURCE_A_ONLY/B_ONLY`도 JSON에 보존합니다.

읽기용 JSON의 `request`가 실제 요청, `response`가 파싱한 응답, `response_text`가 저장된 출력 본문, `result`가 상태·형식 오류·사용량입니다. `records`의 경로는 실험 실행 폴더 기준입니다. 시도하지 않은 조건은 호출 JSON을 만들지 않으며 결과 목록에 NOT_RUN으로 남깁니다.

원응답을 덮어쓰지 않습니다. 한도 초과 후 재개하면 같은 요청 ID 아래 새 시도를 기록하며, 성공한 응답을 다시 호출하지 않습니다. 사용 토큰의 API 환산액과 실제 청구액을 구분합니다.
