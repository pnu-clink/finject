# {run_id} — 캐시를 끈 Luna API 재실행

**{requests:,}요청·{attempts:,}시도 수집 완료. 캐시 읽기 0·쓰기 0. 사용량 기반 비용 ${cost}.** 실제 청구서를 대조한 금액은 아닙니다. 원기록 검증은 {status}입니다.

원문 100개·변형 700개는 exp-004와 같고 프롬프트·V4 응답 스키마·요청 순서도 유지했습니다. 달라진 것은 구독 CLI에서 유료 API로의 전환, 명시적 캐시 해제, 고정 동시 처리 {concurrency}개입니다. exp-005는 CLI 사전 검사 차단 이력으로 보존합니다. 입력·조건별 해시와 전환 승인은 [api-transition.json](api-transition.json)에 있습니다.

호출 기록 구간은 {first_call}부터 {last_response}까지입니다. 첫 off/on 각 1요청을 확인한 뒤 최대 200개씩 처리했습니다. 제공자 비동기 Batch가 아닌 Python 병렬 처리이며 Batch 할인은 적용하지 않았습니다. 첫 두 요청도 전체 {requests:,}건에 포함됩니다.

## 실행·캐시·비용

형식 통과 {valid:,}건, 형식 실패 {failed:,}건입니다. 원 API 응답과 저장된 사용량을 모두 대조했습니다. 반환된 모델과 캐시 모드, 요청의 explicit/no-breakpoint 설정을 함께 확인했습니다. 응답 설정에 보관 기간 `ttl=30m`이 나타나더라도 그것만으로 캐시를 썼다는 뜻은 아닙니다. 실제 반환된 읽기·쓰기 토큰을 기준으로 검증했습니다.

{usage_table}

reasoning은 전체 출력의 일부입니다. 중복 합산하지 않습니다. 실제 청구액은 미확인이고 사용량×일반 API 단가의 추정치를 기록합니다. 세부 원기록은 [검증 README](api-verification/README.md), 전체 조건별 집계는 [REPORT.md](REPORT.md)에 있습니다.

## 원본 100문항의 숫자 비교

{baseline_table}

숫자 일치는 부호를 복원한 answer와 저장된 원문 정답의 직접 일치입니다. 각 조건의 분모는 항상 100개입니다. 형식 실패와 유보를 빼고 분모를 줄이지 않습니다. 이 비율만으로 계산 과정·정답의 의미까지 검증했다고 해석하지 않습니다.

## 형식 실패의 원인

- {abstention_failures}건: `status=abstained`인데 answer와 negative가 null이 아닙니다. status·숫자·부호의 조합 규칙을 위반했습니다. 이 중 숫자 0을 채운 응답은 {zero_placeholders}건이며, 전부 같은 0 채우기 오류는 아닙니다.
- {precision_failures}건: 전달한 `decimal_places`와 숫자 문자열의 소수 자릿수가 다릅니다. 계산값이 맞는 응답과 실제 숫자 불일치를 따로 봐야 합니다.

V4 JSON Schema는 각 필드의 타입을 제한하지만 status에 따른 필드 조합과 요청별 소수 자릿수는 추가 Python 검사로 확인합니다. 따라서 JSON으로 정상 수신했어도 형식 실패가 될 수 있습니다. 원래 입력과 점수는 바꾸지 않았습니다. 전수 실패 상세는 [ANALYSIS.md](ANALYSIS.md)와 [실패 목록](analysis/luna-api-failures.md), 실제 근거를 대조한 사례는 [CASE-STUDIES.md](CASE-STUDIES.md)를 읽으세요.

## 같은 문장이 캐시 사용의 증거인가

동일 Q/C·동일 P0 또는 P1을 가진 off/on 응답을 한 쌍으로 비교했습니다. 원문은 100쌍, 변형은 700×2프롬프트=1,400쌍입니다. 각 쌍을 구성하는 두 API 응답의 캐시 읽기·쓰기는 모두 0입니다.

{pair_table}

캐시 미사용 기록에서도 응답이 완전히 같은 쌍이 있습니다. **문장 또는 응답 JSON의 동일성만으로 캐시 사용 여부를 판정할 수 없습니다.** test-0006의 새 결과와 동일 응답 사례는 [검증 자료](api-verification/README.md)에 있습니다.

## 해석 범위

캐시를 끈 API 안에서 off/on을 비교할 수 있습니다. exp-004 CLI와의 차이에는 기본 지시문·전송 구조 변경도 포함되므로 캐시 제거 하나만의 효과라고 주장하지 않습니다. 실험 2의 유보 선언 빈도는 관찰값이며 유보의 적절성에 대한 최종 채점은 아직 미평가입니다. 루브릭 작업은 재개하지 않았습니다.
