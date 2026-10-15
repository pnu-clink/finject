# 1차 원응답 재검토 · 먼저 확인할 자료

실행: **{{run}}** · 정리 시각: {{updated}}

**현재 단계는 자료 확인입니다. Codex의 새 내용 판정과 개선안은 아직 작성하지 않았습니다.** 대상 LLM은 API로 문제를 풀고, 그 응답은 이 Codex 대화에서 직접 분석합니다. 분석 결과를 사용자에게 보여드리고 개선안을 함께 정한 뒤에만 다음 실험을 진행합니다.

앞선 동일 Luna API의 입력·응답 판정과 재검토는 이번 분석의 근거에서 제외합니다. 그 판정으로 만든 1·2·3차 적절률·개선/악화 비교와 논문 해석은 보류입니다. 실제 풀이 원응답·비용·기존 점수는 삭제하거나 바꾸지 않습니다.

## 00 · 이번에 읽을 범위

|자료|확인된 내용|
|---|---|
|대상|동일 원본 100개와 각 원본의 7변형, 총 800개 입력|
|원본 풀이|Unguided Solving × Reasoning OFF/ON = 200응답|
|변형 풀이|Unguided / Criteria-Guided Solving × Reasoning OFF/ON = 2,800응답|
|실행|GPT-6-Luna · OpenAI Native Batch · 반환 응답 3,000건|
|추론 설정|OFF = none / ON = medium|
|출력 제한|max_output_tokens = 8,192; explanation 최대 2,000자; evidence 최대 12개·각 1,500자|
|선정 범위|제작 자동 검사를 통과한 원본·7변형 세트 100개. 무작위 표본이 아니며 원본의 사람 판단 기록은 PENDING|
|진행 중인 작업|입력·실제 요청·출력의 연결과 기록 집계만 확인. 새 API 호출 0회|

## 01 · 입력 → 지시 → 실제 요청

|순서|자료|무엇을 확인하는가|
|---|---|---|
|1|[public.jsonl](../../01-input/public.jsonl)|800행. 풀이용 question/context/answer_format.decimal_places와 연결용 item_id. 실제 user 메시지에는 Q/C·precision 세 필드만 전달|
|2|[private.jsonl](../../01-input/private.jsonl)|800행. 평가 시 볼 원본 정답·참조 정보·제작 유형. 대상 모델의 문제 풀이 입력과 분리|
|3|[공통 지시](../../00-definition/common.md), [일반 풀이 지시](../../00-definition/p0-standard.md), [기준에 따른 풀이 지시](../../00-definition/p1-abstention-aware.md)|작업 폴더의 최신본이 아니라 **1차 호출 당시 동결본**|
|4|[공통 응답 schema](../../00-definition/response.schema.json)|두 지시 조건이 공유하는 출력 필드와 자료형|
|5|`luna-api/01-requests/manifest.jsonl`|3,000개 요청의 문항·유형·조건과 실제 input/prompt/schema 연결. 이 파일 전체를 풀이 모델에게 보내는 것은 아님|
|6|`luna-api/02-batches/batch-001/input.jsonl`|API에 전달한 model/instructions/input/reasoning/text.format/max_output_tokens 확인|

전송 파일의 3,000개 user 입력을 public과 대조했고, question/context/answer_format만 포함하며 precision이 전달된 것을 확인했습니다. private 정보를 끼워 넣어 입력을 완성하지 않습니다.

manifest와 Batch 전송 파일은 각각 약 27MB인 전체 보관본입니다. 화면에서는 아래 **100문항의 실제 요청·응답 링크**로 나누어 읽습니다. 각 문항의 호출 JSON에서 `request.input`, `request.prompt`, `request.response_schema`를 함께 볼 수 있습니다.

## 02 · 무엇을 반환받았는가

|필드|모델이 작성하는 내용|다음 분석에서 확인할 내용|
|---|---|---|
|answer|최종 숫자 또는 null|요청한 양·부호·단위·precision에 맞는가|
|answer_meta|negative와 scale; answer=null이면 둘 다 null|답과 설명의 표현이 일치하는가|
|explanation|계산과 판단 이유; Criteria-Guided Solving은 Classification/Response 선언 포함|입력의 관계를 지켰는가; 분류와 행동이 일치하는가|
|evidence|context에서 그대로 가져온 인용 배열|인용이 존재하는가와 그 인용이 실제 풀이를 뒷받침하는가를 구분|

[결과 연결 목록](../../luna-api/03-results/results.jsonl)의 `call_path`는 요청·응답을 한 파일로 연결하고, `result_path`는 저장 검사 기록, 호출 파일의 `records.raw_response_path`는 제공자 원응답으로 연결됩니다. 아래 문항 목록의 링크로 실제 파일을 열 수 있습니다.

## 03 · 내용 판정 없이 확인되는 수치

저장된 형식 검사: **{{valid}} / 3,000 통과**. 형식 통과는 풀이·논리·분류가 맞다는 뜻이 아닙니다.

|원본 조건|숫자 일치|숫자 불일치|숫자 답 없음|계획|
|---|---:|---:|---:|---:|
{{original_counts}}

아래 셀은 **숫자 응답 / null 응답**입니다. 모두 실제 `answer` 값의 관찰이며, null을 적절한 유보나 오답으로 판정하지 않았습니다. 각 변형·조건의 분모는 100개입니다.

|입력 유형|Unguided · OFF|Unguided · ON|Criteria-Guided · OFF|Criteria-Guided · ON|
|---|---:|---:|---:|---:|
{{answer_counts}}

## 04 · 한 원본을 따라 자료 열기

문항 번호 오름차순의 첫 문항 **{{sample_case}}**를 자료 연결 예시로 사용합니다. 잘 풀거나 못 푼 사례를 골랐다는 의미가 아닙니다.

질문: {{sample_question}}

precision: {{sample_precision}}자리 · 평가 참조값: {{sample_reference}}. 참조값은 private에서 읽은 평가용 정보입니다.

### 원본의 실제 응답 두 개

{{sample_original}}

### 같은 문항의 첫 변형 · IC_VALUE_01_BEFORE

원본과 변형의 context 차이는 아래 호출 파일의 request.input.context 또는 뷰어의 **문항 비교**에서 확인합니다. 네 응답을 읽기 전에 실제로 어떤 문장을 전달했는지부터 확인합니다.

{{sample_variant}}

## 05 · 원본 100개와 요청·출력 찾아보기

**OFF/ON 열은 숫자 일치 여부만** 표시합니다. 논리·근거·분류 타당성을 뜻하지 않습니다. 각 호출 파일에서 해당 문항의 요청·최종 JSON·제공자 원응답 경로를 확인할 수 있습니다. 변형 4조건 전체는 뷰어의 같은 문항에서 선택합니다.

|원문|평가 참조값|원본 OFF|원본 ON|첫 변형의 네 조건|
|---|---:|---|---|---|
{{case_index}}

## 06 · 이후 분석과 토의의 순서

|단계|담당·할 일|보여드릴 자료|현재 상태|
|---|---|---|---|
|자료 확인|Codex가 저장 입력·지시·원응답 연결|이 문서와 실제 호출 JSON|준비 완료 · 사용자 확인 전|
|내용 분석|Codex가 Q/C와 answer/explanation/evidence를 직접 대조|문항·조건별 관찰, 계산 근거, 반례, 판단 불가 이유|아직 시작하지 않음|
|조건 비교|Codex가 원본 OFF/ON, 7유형×4조건, 역전 사례를 연결|분모가 명시된 비교와 원문 근거|내용 분석 뒤 진행|
|개선안 토의|분석 결과를 제시하고 사용자와 변경·유지 사항 결정|제안과 합의 내용을 구분한 변경안|미합의|
|다음 실험|합의한 변경만 적용해 대상 LLM에 호출|새 요청·원응답|시작하지 않음|

계산 보조와 집계는 로컬 코드로 할 수 있지만 의미 판단을 다른 API 모델에 맡기지 않습니다. 이 단계에서 프롬프트·schema·정답·분모를 고치거나 논문의 새 결론을 작성하지 않습니다.

생성: `src/finarch/experiments/02-analysis/legacy/content-analysis/codex_review_materials.py` · 원본 연결·집계 전용 · API 호출 없음.
