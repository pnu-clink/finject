# 실험 구조 정리 — 단계·run 파일·src 책임 연결

[실험 전체](../../../docs/02-experiments/README.md) · [Analysis](../../../docs/02-experiments/02_analysis/README.md) · [소스 대응표](../../../src/finarch/experiments/README.md) · [문서 뷰어](http://127.0.0.1:8893/?run=20260927-experiment-documentation&doc=docs%2F02-experiments%2FREADME.md)

최신 정리는 **Analysis = 결과 취합 → 관계 비교 → 연구 해석**입니다. 7개 분석 주제를 세 단계에 배치하고, 문항 자체 답변 가능성 검증을 Analysis의 선행 조건에서 제거했습니다. 기존 E04의 형식 검사와 옛 A01의 숫자 비교 책임도 구분해 이관 방향을 명시했습니다.

**문서 구조에 맞춘 새 Analysis를 006에 적용했습니다.** 005의 Evaluation은 동일 사본으로 보존하고 A01 취합 → A02 비교 → A03 현재 Codex 해석만 수행했습니다. [006 결과](../../experiments-run/20260927-exp-006/README.md)와 [뷰어](http://127.0.0.1:8894/?run=20260927-exp-006&tab=analysis)를 확인할 수 있습니다. Evaluation 소스 재배치는 남아 있으며, 후속 모델 호출과 개선안 적용은 이번 작업에 포함하지 않았습니다.

## 읽는 순서와 파일 역할

|순서|파일|무엇을 확인하는가|
|---|---|---|
|1|[실험 전체](../../../docs/02-experiments/README.md)|Input/Evaluation/Analysis 흐름과 목표 run 구조|
|2|[Analysis 단계](../../../docs/02-experiments/02_analysis/README.md)|A01/A02/A03의 역할·입출력·7개 분석 주제|
|3|[src README](../../../src/finarch/experiments/README.md)|현재 실행 파일과 목표 소스 경로·이관 순서|
|4|[source-map.json](source-map.json)|구현된 함수 참조와 PLANNED 단계/파일을 구분한 등록표|
|5|[run-layout-reference.json](run-layout-reference.json)|실제 과거/현행 run 표본과 006 실제 산출물 및 단계 계약|
|6|[migration.json](migration.json), [변경 직전 보관본](../../../archive/20260927-experiment-pipeline-reorganization/analysis-before-results-focus/README.md)|기존 문서의 이관·원본 보존|
|7|[validation.json](validation.json), [events.jsonl](events.jsonl)|최신 문서/링크/보관 해시 검사와 구조 갱신·화면 확인 이력|
|8|[tests.log](tests.log), [ui-review.json](ui-review.json)|이 작업 run에서 앞서 수행한 입력 계약/뷰어 검사 이력. 새 Analysis 실행기의 검증을 뜻하지 않음|

이전에 정리한 public Q/C·precision / private 평가 전용 경계와 모델별 manifest 통합은 유지합니다. [입력 예시](01-input-example/README.md)와 [private 접근 조사](private-access-audit.json)는 그때의 실제 자료입니다. 별도 input-selection을 만들지 않습니다.

과거 실험 원응답·점수·입력은 보존합니다. 새 구조를 실제 실행에 적용할 때에는 소스 이관·같은 입력/분모/원응답 연결 확인·뷰어 연결을 거쳐야 합니다. 이번 문서 검사는 문항의 정답·의미 타당성 검사나 사용자의 최종 검토 완료가 아닙니다.

이 README는 `src/finarch/documentation/templates/experiment-documentation-run.md`에서 생성합니다.
