# 원본 R-off/R-on 짝과 변형 조건 분석 · 저장 결과 재분석

분석한 실행: {{run_ids}} · 생성: {{generated_at}} · 새 모델 호출: **0건**.

1. [analysis.md](analysis.md): 원문 단위 R-off/R-on 짝, 역전 사례와 논문에서 사용할 수 있는 범위를 먼저 읽습니다.
2. [summary.json](summary.json): 실행별 5분류와 7종×4조건 집계, 실제 문항 ID를 읽습니다. 숫자/null은 의미 정답이 아닙니다.
3. [source-hashes.json](source-hashes.json): 읽은 `results.jsonl`·private 입력·config의 SHA-256을 확인합니다. 원본 파일은 수정하지 않았습니다.
4. [validation.json](validation.json): 요청·원문·변형 조건 수와 숫자 판정/미평가 보존을 확인합니다.
5. [events.jsonl](events.jsonl): 이 재분석의 기록입니다.

재생성: `node src/finarch/experiments/02-analysis/legacy/content-analysis/content_analysis_report.mjs`. 공통 [실험 뷰어](http://127.0.0.1:8894/?run=20260923-exp-007&tab=analysis)에서 같은 실행을 골라 실제 문항과 원응답을 확인합니다. [문서 뷰어](http://127.0.0.1:8895/?run=20260923-experiment-improvement)에서는 이 보고서를 읽습니다. 이 README는 `experiment-content-analysis-report.md` 템플릿에서 생성합니다.
