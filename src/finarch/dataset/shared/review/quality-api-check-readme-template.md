# Luna low 정규 감사 4건 + EA gate — {run_id}

`g03_verification.run → audit_one → registered cli.call → complete_api`의 기존 경로를 사용합니다. 별도 HTTP/우회 runner는 없습니다. 테스트 config 복사본만 enabled이며 원 config·profiles·frozen624·A100은 변경하지 않았습니다.

## 읽는 순서

1. `call-plan.json`: 모델 gpt-5.6-luna / low, 4건 순차·자동retry0·최대허용6, 출력8192/총32768 한도. 제공 snapshot단가로6회 보수 토큰비용상한0.098304달러(승인상한0.50달러 이내).
2. `quality-api-check.json`, `summary.json`: 감사 결과와 EA gate 결합을 구분합니다. EA 알려진 복원반례는 감사PASS여도 FAIL이어야 합니다.
3. 각 case의 `03-validation/audit/01-input.json` 및 `01-input/`: 실제 wire model/effort, prompt·response schema·token count·api-start.
4. `02-raw-response/api-execution.json`, `03-result/usage.json`: 원응답·토큰·snapshot 비용추정. 실패 시 schema-check/token-budget/API HTTP 오류 기록을 읽습니다. token count 요청과 생성 호출 수는 따로 셉니다.
5. 각 case의 `03-validation/03-result.json`, `05-recovery-screen.json`, `result.json`: 기존3축 감사와 별도 제한 EA gate.
6. `manifest.json`, `events.jsonl`, `checks.txt`: 입력 불변 hash, 실제 시작/완료와 로컬 회귀.

공통8892 viewer의 `{run_id}` 실행에서 실제 저장값을 읽습니다. 보고서 조회는 모델을 호출하지 않습니다. 화면은 private 연구용입니다.

## 실제 결과

```json
{summary}
```

샘플4건의 결과를624 전체 품질/독립 사람 검토/Qwen baseline으로 확대하지 않습니다. 비용은 저장단가에 따른 추정이며 청구서가 아닙니다. 오류도 호출기록에 남기며 자동/숨은 재호출을 하지 않습니다. 신규 output만 허용합니다.
