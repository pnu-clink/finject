# A100 실험 자료 — 읽기 시점 보관본

읽는 순서: [관찰·해석](analysis.md) → [원격 집계 원본](source/summary.json) → [실패 원본](source/FAILURES.md) → [전송 출처·해시](transfer.json).

원격 작업 폴더는 `/home/clink-wooix/workspace/fexperiment/gpu2-finance-timing-20260921`입니다. 이 작업은 보고·집계 파일 9개를 SCP로 읽었으며 원격 서비스·실험·코드를 변경하지 않았습니다. 여러 파일을 한 순간에 동결한 snapshot은 아니므로 파일별 기록 시각을 구별합니다. 원격 문서의 상대 링크는 당시 원격 위치를 가리키며 이번 보관본에 모든 대상이 포함되지는 않습니다.

`source/`는 가져온 바이트를 보존합니다. `analysis.md`는 이번 작업의 해석이며 새 원격 실행 결과가 아닙니다. 모델별 원응답은 가져오지 않았으므로 해당 모델의 의미 대응을 직접 채점하지 않았습니다. 공통 뷰어의 `20260923-experiment-improvement`에서 함께 읽습니다.

이 README는 `src/finarch/experiments/02-analysis/legacy/comparison/a100-review-template.md`에서 생성합니다.
