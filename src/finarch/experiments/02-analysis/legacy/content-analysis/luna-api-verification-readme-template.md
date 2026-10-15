# {run_id} API 원기록 검증

검증 시각: {checked_at}. 결과: **{status}**. 이 검증에서 추가 모델 호출은 0건입니다.

1. [실행 요약](../RUN-SUMMARY.md): 완료 수·비용·원본 숫자 비교·응답 동일성.
2. [verification.json](verification.json): {requests}요청의 원 API 사용량과 캐시 제어·모델·응답 상태 확인 결과.
3. [raw-hashes.json](raw-hashes.json): 시도별 실제 전송 JSON과 원응답 파일의 SHA-256.
4. [test-0006.json](test-0006.json): 사용자가 지적한 문항의 API off/on 응답과 사용량.
5. [identical-original-example.json](identical-original-example.json): 캐시 읽기·쓰기 0에서도 JSON 전체가 같은 원문 응답 쌍.
6. [events.jsonl](../events.jsonl): 준비·호출 묶음·요청 완료·분석·원기록 검증 순서.

재생성 명령: `PYTHONPATH=src .venv/bin/python -m finarch.experiments.02-analysis.legacy.content-analysis.luna_api_review --run reports/experiments-run/{run_id}`. 저장된 결과만 읽습니다. README는 `src/finarch/experiments/02-analysis/legacy/content-analysis/luna-api-verification-readme-template.md`에서 생성됩니다. 별도 HTML을 만들지 않으며 Markdown 패널과 실험 전용 뷰어에서 원기록을 확인합니다.
