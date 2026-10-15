# JSON 본문 어댑터 전체 검사

실행: {run_id} · FinanceReasoning 원천 {source_total}건 중 비어 있지 않은 JSON 본문 {json_targets}건을 대상으로 검사했습니다.

변환 통과 {passed}건 · 실패 {failed}건 · LLM 호출 0회. 이는 표현·자료형·원문 위치·입력 스키마의 검사이며, 풀이 정답이나 의미 타당성을 검증한 결과가 아닙니다.

|원천|전체|검사 대상|통과|실패|빈 JSON 제외|
|---|---:|---:|---:|---:|---:|
{counts_table}

빈 JSON {empty_json_context}건과 JSON 객체·배열 본문이 아닌 {non_json_context}건은 이번 검사 대상이 아닙니다. 기존 문항 선정 정책을 변경하지 않았습니다.

## 어댑터 자동 적용 기준

원천 스키마에 따라 finance 또는 tatqa 어댑터를 선택합니다. Finance 어댑터는 실제 context가 비어 있지 않은 JSON이면 표 변환을 적용하고, 일반 본문이면 그대로 구성합니다. 같은 출처에도 두 형식이 섞일 수 있으므로 출처 ID만으로 변환을 강제하지 않습니다. TAT-QA 표·문단은 기존 원천 구조를 사용합니다.

전체 입력 생성 경로는 full_finance.prepare → adapters.finance → content.assemble → JSON 값·위치 대조 → prepared.input 스키마 검사입니다. 원본은 provider-records.json에 남고 PoT 숫자 위치는 변환된 context에서 새로 등록합니다.

## 읽는 순서

1. [summary.json](summary.json): 대상 분모와 변환 결과.
2. [json-context-adapter-check.json](json-context-adapter-check.json): 문항별 원문, 변환된 표, 자료형·원문 위치 대조.
3. [prepared-input.json](prepared-input.json): 새 어댑터가 구성한 공통 입력. 이번 검사용 자료이며 기존 run을 덮어쓰지 않았습니다.
4. [raw-records.json](raw-records.json): 검사 대상의 원천 레코드 사본.
5. [checks.jsonl](checks.jsonl): 문항별 실제 검사 로그.
6. [manifest.json](manifest.json): 원천의 검사 전후 해시와 산출물 해시.

## 화면에서 확인

[공통 데이터셋 뷰어](http://127.0.0.1:8893/?run={run_id})의 실행 선택에서 이 기록을 엽니다. 왼쪽에서 문항을 고르면 질문, 원본 JSON, 변환된 표, 칸별 원문 위치·자료형을 확인할 수 있습니다. 결과 폴더에 별도 HTML을 생성하지 않습니다.

## 확인 범위

- 객체 표는 원문에 명시된 연속된 그룹 이름을 제목으로 사용하며 행 순서를 유지합니다.
- 숫자 리터럴의 표기와 숫자·문자열·null·boolean 자료형을 보존합니다.
- 빈 문자열, 원래 없던 칸, 대시 문자열을 구분합니다. 대시를 0으로 바꾸지 않습니다.
- 기존 표 문자열을 감싼 배열은 문자열을 풀고 원문 위치를 연결합니다.
- 변환된 칸을 원본 토큰과 대조하고 숫자·표 좌표·전체 입력 스키마를 검사합니다.
- 원천 파일은 전후 해시가 동일합니다. 기존 Preparation·Generation 결과는 수정하지 않았습니다.
- 실제 원천에 없는 깊은 중첩 JSON 전체를 지원한다는 검증이 아닙니다. 미지원 구조와 중복 key는 명시적 오류가 됩니다.

새 입력 생성부터 이 변환을 사용합니다. 기존 run에 적용하려면 해당 입력의 PoT 숫자 위치와 그래프 연결을 새 본문에 맞춰 다시 검증해야 합니다.

## 연결 재검증

실제 전체 입력 생성 경로·일반 본문 보존·동일 출처의 혼합 형식은 다음 검사로 확인할 수 있습니다. 임시 폴더에 입력을 만들며 모델을 호출하지 않습니다.

```sh
PYTHONPATH=src .venv/bin/python -m unittest finarch.dataset.checks.test_json_context_adapter
```

이번 추가 통합 확인 로그는 adapter-integration-tests.log에, 문서 연결 확인은 adapter-integration-documentation.log에 저장합니다. 로그의 PASS는 입력 변환·연결 검사이며 의미 검증은 아닙니다.
