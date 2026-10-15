# QI01 제한 복원 검사 · 로컬 결과

이 실행은 저장된 최종 본문과 정적 fixture를 읽는 로컬 검사입니다. 데이터 생성·LLM 감사·대상 모델 실험이 아니며 API 호출은 0회입니다. 기존 20260916-001 결과와 동결 데이터는 수정하지 않습니다.

- 실행 ID: `{run_id}`
- 로컬 검사: {tests_run}개, 실패 {failures}개, 오류 {errors}개
- 읽는 순서: `summary.json` → `tests.txt` → 문항 폴더의 `observation.json` → `03-validation/05-recovery-screen.json` → `run.json`
- 공통 뷰어: [이 실행 열기](http://127.0.0.1:8893/?run={run_id}). 실행과 문항을 선택한 뒤 결과 파일에서 실제 JSON의 복원식·인용 위치·판정 범위를 읽습니다. 실행별 HTML은 만들지 않습니다.
- `test-0026-06`: 삭제값 428501, 평균 425855를 남은 표로 복원합니다.
- `test-0074-06`, `test-0074-07`: 닫힌 세 자산 비중에서 각각 40%, 30%를 복원합니다.
- `viewer-check.json`: 공통 뷰어의 실제 자료 읽기 함수에서 세 결과를 읽었는지 확인한 기록입니다. 사용자 화면 확인 완료를 뜻하지 않습니다.

정책은 기본 off입니다. 새 실행에서 `ea_recovery_policy.enabled=true`일 때만 계획 미리보기·최종 본문 검사·별도 차단 판정이 작동합니다. 기존 LLM audit v3와 `full_EA_verdict=NOT_EVALUATED`는 유지합니다. RECOVERABLE은 등록 범위의 실제 반례이며, UNKNOWN은 EA 성립이나 불성립의 확정 판정이 아닙니다.

첫 버전은 두 등록 grammar만 지원합니다: 연속한 Current Federal/State 행과 빈 라벨 소계가 있는 2개 연도 세금 표, 전체가 세 자산임을 명시한 포트폴리오 배분 문장. 지원 구조 안의 공백·회사명·연도·자산명 변형은 검사합니다. 임의의 동의어·일반 표·다른 자산 수·단위 변환·직접 재진술·범용 solver는 지원하지 않으며 UNKNOWN입니다. 실제 첫 버전은 RECOVERABLE 또는 UNKNOWN을 반환하며 NO_WITNESS_IN_SCOPE를 통과 근거로 내보내지 않습니다.

대상 재선정·06/07 후보 공동 예약·재선정 예산/resume·두 세계 구성은 보류했습니다. handler에는 이 두 차단 이유를 LLM에 넘기지 않는 종료 분기만 있습니다. 이번 판정으로 기존 문항을 보정 완료했다고 주장하지 않습니다.

초기 검사 중 테스트 입력의 reference type을 잘못 지정한 1건을 `integer`로 수정했습니다(숫자 변환 규칙 오류가 아닙니다). 넓힌 기존 검사 46개 중 44개 통과, Preparation의 `test_graph_mismatch_does_not_publish_accepted_graph`(question fixture 누락)와 `test_pot_request_preserves_metadata_but_excludes_gold`(answer_metadata 기대값 차이)는 범위 밖 실패로 남겼습니다. 최종 아래 검사 집합은 QI01과 직접 연결된 회귀 검사만 실행합니다. 제외한 실패가 해결되었다는 뜻은 아닙니다.

재현 명령: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m finarch.dataset.checks.run_qi01_checks --output reports/run/새로운-QI01-실행명`. 기존 결과 폴더 덮어쓰기는 거절합니다.
