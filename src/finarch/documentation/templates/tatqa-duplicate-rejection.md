# TAT-QA · CodeTAT-QA 중복 제외

현재 TAT-QA 실행 `20261003-003`을 FinanceReasoning의 **CodeTAT-QA 288건 전체**와 비교했습니다. CodeTAT-QA의 자동 검사 실패 여부와 관계없이 원본 문항을 대조했습니다.

|항목|개수|
|---|---:|
|TAT-QA 비교 대상|717|
|CodeTAT-QA 비교 대상|288|
|원본 질문·표가 일치하는 대응|281|
|Reject 처리한 TAT-QA 문항|280|
|질문 차이로 중복 미확정인 CodeTAT-QA 문항|7|
|평가자용 HTML 대상, 처리 전 → 후|512 → 291|

CodeTAT-QA 2건이 TAT-QA `test-0294` 하나와 대응하여, 281개 대응이 280개 문항에 해당합니다. 제외 문항 중 Preparation 자동 통과는 270개, 자동 실패는 10개입니다. 기존에 7개 유형을 모두 통과해 HTML 대상이었던 중복 221개가 제외됩니다.

## 읽는 순서

1. [plan.json](plan.json): CodeTAT-QA 출처 ID → TAT-QA 원본 question UID·document UID·현재 문제번호, 양쪽 질문과 실제 표의 대응 행을 읽습니다.
2. [result.json](result.json): Reject 적용·원본 해시 보존·7개 통과 문항의 내보내기 제외 여부를 확인합니다.
3. [events.jsonl](events.jsonl): 문항별 Reject 저장 이력을 확인합니다. [prior-decisions.json](prior-decisions.json)은 적용 전 사람 판정입니다.
4. [공통 뷰어](http://127.0.0.1:8893/?run=20261003-003&case=test-0231&stage=07-human-review): TAT-QA `test-0231`의 Reject와 출처 이유를 확인합니다. 이는 FinanceReasoning `test-0001`, `CodeTAT-QA-test-8`과 같은 질문·표입니다.

## 기준과 적용 범위

FinanceReasoning 원천 파일의 해시·`source`·질문을 확인하고, TAT-QA 원천의 question UID·질문·document UID·표가 제작 입력과 같은지 검증했습니다. 질문 비교에서 추가된 `Answer to/as ...` 자리수 지시와 따옴표·대소문자·공백만 정규화했습니다. 세 가지 문구 차이는 따로 확인했습니다: `equiption/equipment` 오탈자, 표에 이미 명시된 `(in thousands)` 단위, 같은 비중 질문의 `the total revenue` 표현입니다.

질문 일치에 더해 **행 이름과 수치의 순서가 같은 표의 최소 두 행**을 확인했습니다. 쉼표·통화·퍼센트·괄호 음수·소수점 표기와 생략된 부가 열은 비교용으로만 정규화했습니다. 원본·생성 본문은 수정하지 않았습니다. 질문이 같은 서로 다른 표는 대응 행 수로 구분하고 동점이면 처리하지 않습니다. 같은 표·같은 정답만으로 중복이라고 판단하지 않습니다.

중복 미확정 7건은 CodeTAT-QA `test-0176`, `test-0421`, `test-0795`, `test-0798`, `test-1124`, `test-1242`, `test-1428`입니다. 절대 변화/비율 변화, 비교 연도, 비용 항목, 분모 범위 등이 달라 자동 Reject하지 않았습니다.

Reject는 현재 실행의 활성 Preparation 차수 `07-human-review/03-record-decision/decision.json`에 기존 저장 함수로 기록합니다. 자동 검사 상태를 FAIL로 바꾸지 않습니다. 문항 전체 제외이므로 이후 평가자용 HTML에서 해당 문항의 7개 유형이 함께 빠집니다. 과거 run·원천 입력·CodeTAT-QA는 보존합니다.

기존에 다운로드한 HTML은 이전 시점의 자료이므로 자동으로 바뀌지 않습니다. **현재 실행에서 평가자용 HTML을 다시 Export**하면 291개가 대상입니다. `results/` 합본은 기존 `export_run_results.py`로 갱신하며, 자동 실패 기록까지 보존하는 합본의 수량은 평가자용 HTML 수량과 다릅니다.

## 재현 명령

```sh
# 출처·질문·표를 비교해 plan.json을 만듭니다. LLM 호출은 없습니다.
PYTHONPATH=src .venv/bin/python -B -m finarch.dataset.90-operations.reject_tatqa_duplicates \
  --run reports/run/20261003-003 \
  --codetat-input data/prepared/finance-reasoning/CodeTAT-QA-20261003/input.json \
  --tatqa-input data/prepared/tatqa/full-20260917/input.json \
  --raw-tatqa data/raw/tatqa-dev.json
# 최초 적용 시 위 명령에 --apply를 붙입니다.
# 계획과 출처·기존 상태가 달라졌으면 적용하지 않습니다.
```

이 README는 `src/finarch/documentation/templates/tatqa-duplicate-rejection.md`에서 생성했습니다. 제작 결과 재생성·LLM 호출·새로운 품질 판정은 수행하지 않았습니다.
