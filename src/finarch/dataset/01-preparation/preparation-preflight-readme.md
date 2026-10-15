# Preparation 소규모 확인 · {run_id}

최신 코드·프롬프트와 새 API 응답으로 {case_count}문항을 동시에 처리했습니다. 자동 검사 {passed}건 통과, {failed}건 미통과입니다. Generation과 전체 대상 배치는 실행하지 않았습니다.

|문항|확인 대상|실행값 / gold|그래프|최종 결과|
|---|---|---|---|---|
{case_rows}

GDP 문항은 첫 PoT에서 `10`을 인용하면서 값은 `-10`으로 선언해 출처 숫자 대조에 실패했습니다. 06-exception-handler가 03-calculation을 대상으로 피드백을 만들었고, 다음 차수에서 `10`을 읽은 뒤 음수 부호를 별도 계산하여 통과했습니다. 원문·gold·첫 실패 응답을 보존했습니다.

## 실행 및 비용

PoT: Sol-medium API. 원문 검토·의미 검증·피드백: Luna-max API. 합산 토큰 상한은 요청별 500,000, 출력 상한은 Sol 128,000 / Luna 32,768입니다.

실행 시간 **{elapsed}초**, 실제 API 생성 요청 **{calls}회**, 사용량 기준 예상 비용 **${cost}**입니다. 캐시·추론 토큰을 포함한 API usage와 공개 요금표로 계산한 값이며 청구서 확정 금액은 아닙니다.

|용도|호출 수|평균 입력 토큰|평균 출력 토큰|평균 합계|예상 비용 USD|
|---|---:|---:|---:|---:|---:|
{usage_rows}

```bash
{command}
```

## 확인 범위

- 원문 검토 → PoT → Python 실행 → 그래프 → 의미 검증 → 최종 상태까지 실제 API로 확인했습니다. 이전 LLM 응답은 가져오지 않았습니다.
- Python·gold 일치와 그래프 비교는 {case_count}건 모두 통과했습니다. 실제 API 동시 실행은 {case_count}건입니다. 200개 동시 worker의 파일 충돌·단일 집계는 별도 로컬 검사입니다.
- API 응답 잘림 {incomplete}건, 통신 실패 {transport_errors}건. 요청당 실제 최대 합산 사용량 {max_tokens}토큰입니다. 50만 한도 도달과 출력 잘림은 서로 다른 오류이며 경계 조건은 모의 응답으로 검사했습니다.
- 중단 ID 재등록·이전 파일 보관·완료 문항 보존은 로컬 모의 검사로 확인했습니다. 실제 유료 호출을 강제로 중단하지 않았습니다. 완료된 run에 `--resume`을 실행하면 `NO_UNFINISHED_CASES`로 추가 API 호출 0회였습니다.
- 소규모 통과는 전체 문항의 의미 타당성·API 200건의 외부 서비스 처리량을 보증하지 않습니다. 429·연결 끊김의 별도 자동 통신 재시도는 아직 없습니다. 중단된 문항은 ID로 재등록해 01-source부터 다시 실행합니다.

## 전체 입력 정정

기존 2,171건에는 본문 문자열 `[]` 121건이 포함돼 있었습니다. 사용자 지정 빈 본문 제외 기준에 맞춰 검사 로직을 보완하고, 새 입력 **2,050건**을 만들었습니다. 보존된 문항의 Q·C·A는 동일합니다. 이전 입력과 이번 6문항의 ID·산출물은 유지합니다.

다음 전체 실행 입력: `data/prepared/finance-reasoning/full-20260917-v2/input.json`. 새 입력은 제외 뒤 번호를 다시 부여하므로 `input-correction.json`에서 raw_id 기준 이전/새 ID를 확인합니다.

## 파일과 읽는 순서

1. 이 문서 → `preflight-summary.json`: 문항별 결과·검사 범위.
2. `scheduler.log`, `checks.log`, `resume-check.json`: 실행·로컬 검사·완료 후 재개 확인.
3. `input-correction.json`: 빈 본문 제외 목록·입력 해시·새 ID 대응.
4. `01-preparation/test-xxxx/NN-round/`: 원문·프롬프트·응답·코드·그래프·검증. GDP의 피드백은 01-round/06-exception-handler에, 실제 전달 기록은 02-round/03-calculation/02-LLM-generate-code에 있습니다.
5. `api-usage/summary.json`: 중복 사본을 제외한 호출·토큰·용도별 비용.

[공통 뷰어](http://127.0.0.1:8892/?run={run_id}&case=test-0458&round=02-round&stage=03-calculation) · [전체 입력 재점검](http://127.0.0.1:8892/?run=20260917-finance-preflight-v2)
