# A04 후속 정리

{run} · A03 연구 발견 {findings}개 → 주제 {groups}개. 동결 Analysis 설정의 모델로 그룹화하고 Python으로 F 대응과 인용을 검사합니다.

## 읽는 순서

1. `state.json` / `summary.json`: 등록된 후속 단계의 처리 상태입니다.
2. `01_findings/summary.json`: D01 연구 발견 그룹·F 원문·조건별 대응표·근거 응답 ID·원천 해시입니다. 개선 토의 안건이나 관찰을 그룹 항목으로 넣지 않습니다.
3. 실험 뷰어 **03 사분면 비교 → D01 연구발견**: 주제를 선택하여 네 풀이 조건과 원래 F 내용을 비교합니다.

발견의 의미가 비슷한 주장을 묶으며 F 원문·반례·대안 설명·한계·판정은 그대로 둡니다. 조건 연결은 F → 인용한 관찰 → 실제 응답의 조건을 따릅니다. 여러 조건을 비교한 F는 여러 칸에 표시되므로 칸별 수를 더하면 고유 발견 수와 다릅니다. 표의 수는 발견 연결 수이며 응답 성공률이나 조건 효과의 크기가 아닙니다.

## 실행

`PYTHONPATH=src .venv/bin/python -u -B -m finarch.experiments.pipeline analysis-postprocess --run reports/experiments-run/{run}`

완료된 A03을 확인하고 A04만 실행합니다. 표준 Analysis pipeline도 A03 수집 다음에 같은 A04를 실행합니다. 명령과 진행은 루트 `pipeline.log`·`events.jsonl`, 시간은 `02_analysis/timing.json`에 기록합니다. 원천 참조 누락·해시 변경은 실패로 남기며 원응답은 바꾸지 않습니다. `prompt.md`·`schema.json`·`manifest.jsonl`은 동결 요청, `calls/`는 실제 모델 요청·원응답입니다. 성공한 저장 결과는 재사용하고 전송 여부가 불분명한 요청은 중복 호출하지 않습니다.
