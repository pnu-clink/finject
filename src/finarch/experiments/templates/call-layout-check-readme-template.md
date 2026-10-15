# 실험 호출 폴더 정리 검사

상태: **{status}** · 확인 시각: {verified_at}

## 읽는 순서

1. [실제 JSON 예시](../../experiments-run/20260920-exp-003/gemini-2.5-flash/calls/test-0006/00-Original/test-0006-P0-R-off.json): 원본 문제의 요청과 응답.
2. [변형 JSON 예시](../../experiments-run/20260920-exp-003/gemini-2.5-flash/calls/test-0006/01-IC-value-before/test-0006-P1-R-on.json): 유보 유도·추론 on 조건.
3. [구조와 읽는 법](../../../../docs/02-experiments/README.md): 전체 유형·필드·코드 책임·실제 순서도.
4. [검증 결과](verification.json): 문항별 파일 수, 현재 결과·원응답 연결, 집계와 비용 불변.
5. [로컬 검사 로그](tests.log): {tests_passed}개 검사 통과. 실제 모델 호출 없음.
6. `exp001-migration.log`, `exp002-migration.log`, `exp003-migration.log`, `root-migration.log`: 프로그램의 실제 정리 로그.

exp-003은 모델당 원문 100개 × 원본 2조건·변형 28조건 = 3,000개, 두 모델 총 6,000개 JSON입니다. exp-001은 이전 선정 기준의 시도 이력이고, exp-002는 미호출로 대체된 실행이므로 호출 JSON이 없습니다.

EA 번호 정정은 각 실행의 `label-migration`에 변경 전 원본·이전 manifest를 보존했습니다. 폴더 이동은 그 이후 원기록 해시와 집계값을 대조했습니다. 원응답·사용량·추정 비용은 그대로이며 새로운 모델 호출은 0건입니다.

이 README는 `src/finarch/experiments/templates/call-layout-check-readme-template.md`에서 생성했습니다. 새 화면이나 HTML을 생성하지 않았습니다.
