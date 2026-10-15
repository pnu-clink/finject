# $model 회수 결과

실행 `$run`: **$responses건 수집**, 로컬 전체 응답 계약 통과 **$valid건 ($valid_rate)**입니다.

읽는 순서: 이 보고서 → [구조화 집계](recovered-summary.json) → [E04 형식 보고서](01_evaluation/04_validation/REPORT.md) → [원본 숫자 비교](01_evaluation/04_validation/numeric-comparisons.jsonl) → [실패 문항](01_evaluation/04_validation/failure-details.jsonl) → [회수 해시 기록](recovery-receipt.json)입니다. 조건별 실제 요청·응답은 [실험 뷰어](http://127.0.0.1:8894/?run=$run&tab=conditions)에서 읽습니다.

## 조건별 결과

$conditions

원격 스키마 통과는 JSON 구조 검사입니다. 로컬 전체 계약 통과는 추가로 classification·숫자/null·부호·scale·소수 자리수 규칙을 확인합니다. 숫자 일치는 원본의 고정 참조와 숫자만 비교하며 의미 정답 판정이 아닙니다. 계획 분모는 각 조건의 원본 1,080개를 유지합니다. 비교 분모는 형식 통과 후 숫자 답을 비교한 원본만 사용합니다.

## 입력 유형별 형식 통과

$types

각 셀은 로컬 전체 계약 통과/계획 응답 수입니다. 실패 문항을 분모에서 빼지 않습니다.

## 입력 유형별 숫자 답 없음

$null_answers

각 셀은 `answer=null`/형식 유효 응답 수입니다. 유효 응답만의 관찰이며, 답 없음이 적절한지 또는 오류를 제대로 검출했는지는 아직 판정하지 않았습니다.

## 분류 기록

$classifications

위 분류는 계약을 통과한 응답의 모델 선언입니다. 분류의 타당성은 아직 의미 검토하지 않았습니다.

## 실패와 한계

$failures

하나의 응답이 여러 규칙을 위반하면 규칙별 수는 중복됩니다. 잘림은 별도 상태이며 원응답은 수정하지 않습니다. [실패 목록](01_evaluation/04_validation/failure-details.jsonl)과 뷰어의 해당 문항에서 실제 내용을 확인할 수 있습니다.

잘린 응답은 원격 `delivery.json`의 usage·finish_reason이 누락된 경우가 있습니다. 실제 `raw-response.json`의 기록으로 로컬 집계를 만들며 누락을 0으로 채우지 않습니다. 최초 로컬 판정은 해당 시도의 `result-before-delivery-metadata-repair.json`에 보존하고 수정 이벤트를 남깁니다. 원격 원응답·수신 기록은 덮어쓰지 않습니다.

## 시간·사용량·캐시

평가 전체 경과 시간은 **$wall**, 처리량은 **초당 $throughput건**입니다. A100 4장 배정 기준 평가 구간은 **$gpu_hours GPU시간**입니다. 모델 로딩 등 평가 이전 시간은 이 수치에 포함하지 않습니다.

$latency

건당 시간은 요청 전송부터 응답 수신까지입니다. 동시 처리하므로 건별 누적 시간을 전체 경과 시간과 구별합니다. 제공자 내부 대기와 추론 시간을 분리해서 측정하지 않았습니다.

실제 서버 설정과 시작·종료 cache 지표는 `remote-evidence/`에 보존합니다. Prefix caching은 OFF이고 시작·종료 hit는 0입니다. 개별 응답의 캐시 토큰 필드는 누락되어 **UNKNOWN_NOT_ZERO**로 유지합니다. 외부 API 호출 비용은 0달러이며 GPU 금액은 미산정입니다. 토큰·추론 토큰·조건별 시간과 유형별 집계는 [recovered-summary.json](recovered-summary.json)에 있습니다.

## 파일 보존과 분석 상태

- `remote-results/`: 원격의 전송 요청·원응답·수신 기록·기본 검사 원본.
- `collection/responses.jsonl`: 원격이 만든 응답 취합본. 원응답의 공급자 필드를 보존합니다.
- `remote-evidence/`: 원격 상태·runtime·로그·프롬프트 사본. 준비 시 동결한 로컬 파일은 덮어쓰지 않습니다.
- `01_evaluation/03_execution/`: 기존 뷰어와 연결한 시도별 원응답·로컬 검사·문항별 조회 파일.
- `_recovery/manifest.json`: 회수 파일 SHA-256 목록.

이번 정리는 Python으로 기존 응답을 검증·집계했습니다. 새 모델 호출은 0건이며 A02·A03 LLM Analysis는 시작하지 않았습니다.
