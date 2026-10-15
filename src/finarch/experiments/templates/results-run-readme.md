# {run} — Evaluation 응답 재사용·별도 Analysis

Evaluation 출처는 **{source}**입니다. 입력·고정 요청·원응답·형식 검사 파일을 바이트 동일하게 보관했습니다. 새 대상 모델 호출은 **0회**, 독립된 반복 실험이 아닙니다. 현재 상태: **{status}**, 계획 응답 **{planned}개**.

|읽는 순서|자료|역할|
|---|---|---|
|1|[config.json](config.json), [manifest.json](manifest.json)|재사용 출처·해시와 선택한 분석 모델·effort·태그|
|2|[00_input](00_input/README.md)|public Q/C·precision과 private 평가 자료|
|3|[Evaluation](01_evaluation/README.md)|원출처의 요청·풀이 원기록·형식 결과. 내부 날짜와 run 표기는 원출처 유지|
|4|[Analysis](02_analysis/README.md)|결과 취합 → 관계 비교 → 연구 해석|
|5|[최종 연구 해석](02_analysis/03_research/findings.md)|관찰 수치·실제 응답·반례·한계·개선 토의|
|6|[events.jsonl](events.jsonl), [state.json](state.json)|이번 분석의 진행·보존 확인 이력|

[실험 뷰어](http://127.0.0.1:8894/?run={run}&tab=analysis)에서 같은 자료를 읽습니다. 문항 답변 가능성 재판정과 과거 분석 LLM 점수는 이번 분석의 선행 조건으로 사용하지 않습니다. 사용자 결정 전에는 새 실험이나 논문 결론을 자동 변경하지 않습니다.

## 사용법과 시작 로그

`PYTHONPATH=src .venv/bin/python -u -B -m finarch.experiments.pipeline analysis --run reports/experiments-run/{run}`으로 A01 → A02 → A03을 실행합니다. 단계 시작 전 `TASK_START`에서 tag·실제 모델·effort·작업·Python/LLM 구분·요청 수·동시 한도를 출력합니다. `pipeline.log`와 `02_analysis/execution.log`에서 확인합니다. Evaluation은 완료된 응답의 재사용이며 새 풀이 요청은 없습니다.
