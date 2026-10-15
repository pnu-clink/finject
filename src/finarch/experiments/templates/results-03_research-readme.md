# A03 — 연구 해석과 개선 토의

{source}의 Evaluation을 읽어 {findings}개 해석을 정리했습니다. {execution_note}

1. [findings.md](findings.md): 수치 → 근거 → 반례·다른 설명 → 주장 한계 → 개선 토의 순서로 읽는 한국어 안내.
2. [findings.json](findings.json): 위 문서와 뷰어가 함께 읽는 기준 데이터. 영어 분석과 한국어 표시 번역을 구분합니다.
3. [manifest.jsonl](manifest.jsonl): 분석 설정·입력·실제 응답 참조와 저장 기록의 연결.
4. [prompt.md](prompt.md), [schema.json](schema.json), [calls](calls/): 분석 지침과 응답 계약·실행별 원응답입니다. 현재 대화 기록과 별도 CLI/API 호출은 실행 방식으로 구분합니다.
5. [state.json](state.json): 완료 상태와 근거로 연결한 {cited}개 응답의 범위. 전체 응답을 재채점했다는 뜻이 아닙니다.

후속 실험은 토의 안건이며 실행하지 않았습니다. [A02 비교](../02_comparison/README.md) · [실행 전체](../../README.md)

## 사용법

상위 Analysis pipeline은 A02 완료 후 주제별·입력 크기별 A03 요청을 생성합니다. 실제 호출 내용·건수는 manifest.jsonl, 지시는 prompt.md, 응답 계약은 schema.json, 원응답은 calls/에서 확인합니다. 호출 수는 고정값이 아닙니다. findings가 저장되어도 토의 안건이 후속 실험 실행 승인으로 바뀌지는 않습니다.
