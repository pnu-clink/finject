# RQ별 연구 해석 통합 안내 · {run}

1. [rq-review.md](rq-review.md): 104개 발견을 9개 상위 항목으로 정리한 RQ1–RQ4 보고서입니다.
2. [rq-review-audit.md](rq-review-audit.md): 모든 F의 주 그룹·보조 그룹·판단 이유를 확인합니다.
3. [rq-review.json](rq-review.json): 현재 대화의 편집 판단, RQ 정의, 원자료 해시와 전체 대응표입니다.
4. [rq-review-validation.json](rq-review-validation.json): 104개 모두 정확히 한 주 그룹에 배정됐는지, 참조와 원자료 해시가 맞는지 확인한 기록입니다. 의미적 정답 검증을 뜻하지 않습니다.
5. [findings.json](findings.json), [findings.md](findings.md): 기존 A03 원본입니다. 대응표의 F 번호로 추적합니다.

로그는 실행 루트의 events.jsonl에 남깁니다. 실험 뷰어에서 이 실행 → 연구 해석 → RQ별 통합 검토를 읽습니다. 렌더링은 src/finarch/experiments/02-analysis/03-research/rq_review.py와 템플릿이 담당하며, 새 모델 호출은 수행하지 않습니다.
