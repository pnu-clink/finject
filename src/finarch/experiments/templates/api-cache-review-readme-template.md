# API 캐시 조사와 test-0006 확인 안내

확인 시각: {checked_at}. 실제 모델 호출은 0건입니다. {run_id}는 `CACHE_POLICY_BLOCKED` 상태를 유지합니다.

1. [API-CACHE-GUIDE.md](../API-CACHE-GUIDE.md): test-0006 사용량, 제공자별 공식 차단 방법, 미확인 사항을 읽습니다.
2. [test-0006.json](test-0006.json): 두 응답의 사용량·원기록 경로·해시·JSON 동일성 확인 결과입니다.
3. [CACHE-AUDIT.md](../CACHE-AUDIT.md), [cache-audit.json](../cache-audit.json): exp-004의 3,000응답을 실제 Codex 쓰기 필드로 다시 집계한 결과입니다.
4. [sources.json](sources.json): 조사한 공식 문서 URL과 확인한 주장입니다. API 동작을 실측한 결과와 구분합니다.
5. [correction.json](correction.json), [superseded](superseded/): 잘못된 쓰기 필드 집계의 정정 내역과 이전 보고서 보존본입니다. 보존본은 현재 판단에 사용하지 않습니다.
6. [verification.json](verification.json), [tests.log](tests.log), [events.jsonl](events.jsonl): 로컬 검사 {tests_run}개 결과, 원기록 검증, 작업 기록입니다.

이 README는 `src/finarch/experiments/templates/api-cache-review-readme-template.md`에서 생성했습니다. 응답 원문·기존 실험의 입력·설정·채점 결과를 바꾸지 않았습니다. 새로운 제공자 전송 경로는 구현하거나 실행하지 않았습니다. Markdown 패널에서 1번 문서를 열어 표와 링크를 확인하실 수 있으며, 별도 HTML을 생성하지 않습니다.
