# 실험 소스 정리 · Analysis TOML 설정

[소스 입구](../../../src/finarch/experiments/README.md) · [설정 안내](../../../config/experiments/README.md) · [문서 뷰어](http://127.0.0.1:8893/?run=20260927-experiment-source-layout)

실험을 일시 중지한 상태에서 소스를 `00-input → 01-evaluation → 02-analysis`로 정리했습니다. 내부 단계는 run의 번호·역할과 대응하며, 전체 pipeline과 단계별 pipeline을 제공합니다. Analysis는 TOML에서 Codex CLI 또는 OpenAI Batch를 선택합니다.

## 파일 역할과 읽는 순서

|순서|파일|확인 내용|
|---|---|---|
|1|[migration.json](migration.json)|이동 전후 경로·원본 해시·보관 위치·참조 변경 목록|
|2|[baseline-checks.json](baseline-checks.json)|이동 전 로컬 검사 상태|
|3|[validation.json](validation.json)|수정 후 로컬 검사·설정 전환·중지 상태·문서·화면 확인 결과|
|4|[events.jsonl](events.jsonl)|작업 순서·검사 결과·모델 호출 수|
|5|[documentation.json](documentation.json)|공통 뷰어가 읽는 소스 안내 문서 목록|
|6|[Analysis 프롬프트 정리](prompt-clarity/README.md)|내부 단계 표현을 실제 입력·집계 설명으로 바꾼 전후 원문·검사|
|7|[시간 기록 로컬 검사](analysis-timing-checks.log) · [뷰어 검사](analysis-timing-viewer-checks.log)|단계·병렬 호출 시간, 중단·실패 기록, 화면 전달 검사|
|8|[시간 기록 확인 결과](analysis-timing-verification.json) · [스키마 복구 검사](analysis-schema-recovery-checks.log) · [진행 상태 검사](analysis-progress-checks.log)|첫 실제 호출·원본 스키마 보존·거절 기록 보존·재개 표시 확인|
|9|[동시 호출 검사](analysis-scheduler-checks.log) · [실행 확인](analysis-scheduler-verification.json)|20건 시작·60초마다 CPU 조건부 증가·기존 호출 보존·화면 확인|
|10|[응답 미확인 ID 검사](analysis-unresolved-ids-checks.log) · [미요청 문항 재개 확인](analysis-unsent-resume-verification.json)|이번 실행에서 생긴 시간 초과도 오류 목록에 포함·기존 4건 원기록 보존·미요청 359건만 재개|
|11|[진행 대시보드 검사](progress-dashboard-checks.log) · [실제 API·화면 확인](progress-dashboard-verification.json) · [그래프 화면](progress-dashboard-graphs.png)|완료·실행 중·대기·오류·남은 건수 일치, 평균에서 미완료·실패 제외, 동시 호출 수·한도 계단형 그래프와 CPU 60% 기준, 5초 자동 조회|

[Luna 진행 대시보드](http://127.0.0.1:8894/?run=20260927-exp-007-luna&tab=progress)는 같은 화면에서 실행을 선택하여 최신 기록을 읽습니다. 동시 호출 수와 CPU 그래프는 같은 시간축을 쓰며, 위쪽 막대에 현재 값과 한도·증설 기준을 표시합니다. 대시보드 검증은 기존 분석의 실행 기록만 읽으며 새 모델 호출을 만들지 않습니다.

시간 기록 기능을 추가한 뒤 사용자 지시로 Luna의 기존 Batch 수집·Analysis를 재개했습니다. 실행 중 실제 측정값은 [Luna 시간 기록](../../experiments-run/20260927-exp-007-luna/02_analysis/timing.md)과 실험 뷰어에서 확인합니다. 아래 소스 정리 당시의 호출 0회 기록과 이후 실행 상태를 구별합니다.

원본은 [보관 폴더](../../../archive/20260927-experiment-source-layout/)에 있습니다. 기존 실행의 prompt/schema·원응답은 이 작업의 수정 대상에 포함되지 않습니다. 숫자 비교와 원응답 검사 책임은 E04에 있고, A01은 그 결과를 취합합니다.

공통 문서 뷰어에서 `20260927-experiment-source-layout` 실행을 선택하면 현재 파일을 읽습니다. 실제 실험 자료는 [실험 뷰어](http://127.0.0.1:8894/)에서 run을 선택해 확인합니다. 결과마다 HTML을 생성하지 않습니다.

이 기록은 코드 구조·로컬 검사의 기록입니다. 실제 API/Codex 분석 완료나 의미적 정답 검증을 뜻하지 않습니다. 신규 모델 호출·Batch 제출·원격 상태 조회는 하지 않았으며, 앞서 제출한 원격 Batch가 제공자에서 계속되는지 여부는 별도입니다.

이 README는 `src/finarch/documentation/templates/experiment-source-layout-log.md`에서 생성합니다.
