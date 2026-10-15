# 스키마 파일 안내

스키마는 **어떤 항목을 어떤 자료형으로 담아야 하는지 정한 규격**입니다. 입력 데이터와 LLM 답변은 서로 다른 규격을 사용합니다.

## 지금 확인할 파일

|용도|정의를 수정하는 파일|자동 생성된 JSON Schema|
|---|---|---|
|준비된 전체 입력|[prepared.py](prepared.py)|[01-preparation.01-source.prepared-input.schema.json](json/01-preparation.01-source.prepared-input.schema.json)|
|POT에 보낼 입력|[llm.py](llm.py)|[01-preparation.03-calculation.pot.request.schema.json](json/01-preparation.03-calculation.pot.request.schema.json)|
|POT 풀이 답변|[llm.py](llm.py)|[01-preparation.03-calculation.pot.response.schema.json](json/01-preparation.03-calculation.pot.response.schema.json)|
|문장 수정 답변|[llm.py](llm.py)|[02-generation.02-generate-text.realization.response.schema.json](json/02-generation.02-generate-text.realization.response.schema.json)|
|의도 감사 답변 초안|[llm.py](llm.py)|[shared.01-02.02-03.review-and-validation.response.schema.json](json/shared.01-02.02-03.review-and-validation.response.schema.json)|

`common.py`는 추가 필드와 자동 타입 변환을 금지합니다. `registry.py`는 이름·버전·상태를 관리하고 JSON Schema를 만듭니다. **[validation.py](validation.py)가 같은 정의를 읽어 실제 Python 검사를 수행합니다.** JSON 파일은 확인·전달용 자동 생성본이며 직접 수정하는 두 번째 원본이 아닙니다. [index.json](json/index.json)에 각 스키마의 버전·해시·준비 상태가 있습니다.

## 스키마 안의 항목 읽는 법

스키마 파일에는 **형식을 설명하는 용어**와 **실제 데이터에 들어갈 항목**이 함께 보입니다. 예를 들어 `properties`는 항목들을 설명하는 자리이고, 그 안의 `facts`는 실제 POT 답변에 들어갈 항목입니다.

|스키마 용어|뜻|이 프로젝트에서 읽는 방법|
|---|---|---|
|`properties`|JSON 객체에 어떤 항목이 있는지 설명합니다.|POT 응답에는 `code`, `facts`, `grounding`이 정의돼 있습니다.|
|`required`|반드시 들어가야 하는 항목 이름의 목록입니다.|목록에 있는 항목이 빠지면 거절합니다. `properties`에 있다는 것만으로 필수라는 뜻은 아닙니다.|
|`type`|값의 자료형입니다.|`string`은 문자열, `integer`는 정수, `boolean`은 true/false, `object`는 이름과 값의 묶음, `array`는 목록입니다.|
|`$defs`|여러 곳에서 사용할 하위 구조의 정의입니다.|`Fact`의 구성은 여기에 정의됩니다.|
|`$ref`|다른 곳에 정의한 구조를 참조합니다.|`#/$defs/Fact`는 이 파일의 Fact 정의를 따르라는 뜻입니다.|
|`additionalProperties`|미리 열거하지 않은 이름을 받을 수 있는지 정합니다.|`false`면 모르는 항목을 거절합니다. POT 응답 v2의 facts는 id를 가진 Fact 객체 목록이며, 각 객체는 정해진 필드만 받습니다.|
|`enum` / `const`|허용된 값의 목록 / 하나의 고정값입니다.|정답 타입은 integer 또는 float입니다.|
|`anyOf` / `oneOf`|나열된 형식 중 하나 이상 / 정확히 하나에 맞아야 합니다.|문자열 또는 null, 출처별 서로 다른 구조 등에 사용합니다.|
|`minLength` / `minItems`|문자열 최소 길이 / 목록 최소 개수입니다.|빈 문자열이나 빈 목록을 허용하지 않는 항목을 표시합니다.|
|`minimum` / `maximum`|숫자의 허용 범위입니다.|정밀도는 0부터 100까지입니다.|
|`title` / `description`|이름과 설명입니다.|설명을 위한 정보이며, 그 문장 자체가 Python 실행 검사는 아닙니다.|
|`$id` / `$schema`|이 스키마의 식별 이름 / JSON Schema 규격입니다.|실행 로그의 문제 ID와는 다른 값입니다.|

**값이 null인 것과 항목이 없는 것은 다릅니다.** 현재 `scale`, `negative`, Fact의 `unit`은 필수 항목입니다. `scale`과 `unit`은 값으로 null을 허용하지만 항목 자체를 생략할 수는 없습니다.

## 준비 입력에 들어가는 내용

[입력 스키마](json/01-preparation.01-source.prepared-input.schema.json)는 **문제들의 목록**을 받습니다. 각 문제는 다음 항목을 모두 가집니다. 생성하는 쪽은 원천 데이터를 읽는 Python 코드입니다.

|항목|뜻|현재 형식·검사|
|---|---|---|
|`id`|이 묶음 안에서 사용하는 문제 번호입니다.|빈 문자열 불가, 묶음 안에서 중복 불가.|
|`raw_id`|원천 문제와 연결하는 번호입니다.|빈 문자열 불가, 묶음 안에서 중복 불가.|
|`context`|원문 문단과 표를 읽을 수 있도록 이어 놓은 본문입니다.|비어 있지 않은 문자열.|
|`question`|원문 질문 하나입니다.|비어 있지 않은 문자열.|
|`source_content`|문단·표·칸의 구조를 담습니다.|문단은 paragraphs, 표는 tables, 표의 행은 rows, 칸은 cells에 있습니다.|
|`context_mapping`|본문의 어느 부분이 원문의 어느 위치에서 왔는지 연결합니다.|각 구간의 문자열이 실제 context와 일치하는지도 Python으로 검사합니다.|
|`reference_answer`|원천 정답을 숫자 문자열로 담습니다.|문자열로 보관해 소수 자릿수를 유지합니다.|
|`reference_answer_type`|원천 정답의 정수·실수 구분입니다.|integer 또는 float.|
|`reference_precision`|원천 정답의 소수 자릿수입니다.|0~100의 정수. 질문의 반올림 지시를 해석한 값은 아닙니다.|
|`answer_metadata`|정답 배율과 부호를 담습니다.|scale과 negative가 필수입니다.|
|`provenance`|원천 데이터셋·파일 버전·해시 등의 출처입니다.|FinanceReasoning은 source_id/level, TAT-QA는 document_id가 추가됩니다.|

`answer_metadata.scale`은 원천에 명시된 배율 문자열입니다. 배율 표기가 없으면 null로 통일합니다. `negative`는 정답에 명시적인 음수 부호가 있으면 true, 없으면 false입니다. 괄호만 보고 음수로 해석하지 않습니다.

### 원문 위치 정보

|항목|뜻|
|---|---|
|`context_span`|context에서 해당 문자열이 시작하고 끝나는 문자 위치입니다. 0부터 세며 시작은 포함하고 끝은 포함하지 않습니다.|
|`source_pointer`|원천 레코드 안에서 문단이나 표 칸을 찾는 경로입니다.|
|`row` / `column`|표 칸의 행·열 번호입니다. 0부터 셉니다.|
|`segments`|문단 또는 칸별로 원문 위치와 본문 위치를 연결한 목록입니다.|
|`numbers`|문자열에서 찾은 숫자 표기 후보들입니다. 금융적 의미까지 확인한 근거라는 뜻은 아닙니다.|
|`source_text_span`|해당 문단·칸 문자열 안에서 숫자가 있는 위치입니다.|
|`source_root`|원천 위치 경로의 기준을 설명합니다. 현재 값은 실행 기록의 raw-record.json 안 record를 가리킵니다. 준비 폴더에 문제별 파일이 다시 있다는 뜻은 아닙니다.|

### JSON 본문을 표로 바꾼 입력 · v2

문단·표 칸·segments에는 선택적인 json_source를 추가합니다. 기존 입력에는 없어도 됩니다. source_pointer가 /context일 때 실제 원천은 JSON을 담은 문자열이며, 그 내부 경로를 별도로 기록합니다.

|항목|뜻|
|---|---|
|json_source.pointer|원문 context 문자열 내부를 JSON으로 읽었을 때의 경로|
|json_source.source_span / raw_text|변환 전 문자열에서 실제 JSON 토큰의 문자 구간과 원래 토큰 표기|
|json_source.value_type|key / string / integer / number / boolean / null 구분|
|json_source.decoded_span|그룹 제목·행 이름 등 표시한 부분이 디코딩된 원문 토큰에서 차지하는 구간|
|json_source.markdown_escaped|표의 구분자·줄바꿈 이스케이프를 적용했는지 여부|

context_span과 숫자 위치는 변환된 context의 위치입니다. JSON 입력 변환기는 raw 토큰의 위치·자료형·값을 함께 대조한 뒤 이 스키마 검사를 진행합니다. [실제 변환 흐름](../../../../docs/01-dataset/00-input/01-selection.md#json-본문-표-변환--in03j).

## POT에 보내는 내용과 돌아오는 내용

POT은 원문과 질문에서 풀이 프로그램을 만드는 단계입니다. **보내는 입력과 받아야 할 답변을 각각 정의합니다.**

### 보내는 입력 — ProgramRequest

|항목|뜻|
|---|---|
|`context`, `question`|원문 본문과 질문입니다.|
|`reference.answer`|작성자가 참고할 수 있도록 허용한 원천 정답입니다.|
|`reference.answer_type`, `reference.precision`|원천 정답의 타입과 소수 자릿수입니다.|
|`provider_record`|작성자에게 허용한 비공개 원천 자료입니다. 원천마다 내용이 달라 JSON 객체의 내부 키를 고정하지 않습니다. 독립 답변 단계에는 보내지 않습니다.|

### 받는 답변 — ProgramResponse

|항목|뜻|필수 여부|
|---|---|---|
|`code`|생성한 Python 풀이 코드입니다.|필수, 빈 문자열 불가.|
|`facts`|풀이에 사용한 숫자와 원문 근거의 목록입니다.|필수, 최소 한 개. 각 항목은 아래 Fact 구조를 따릅니다.|
|`grounding`|이 근거들이 풀이에 어떻게 사용되는지 설명한 문장입니다.|필수, 빈 문자열 불가.|

**Fact 하나는 ‘어떤 원문 숫자를 가져다 썼는지’에 대한 기록입니다.** `facts`는 id가 있는 Fact 목록입니다. 예를 들어 id가 revenue인 항목이 매출 근거입니다. 응답 검사 후 실행할 때만 id로 찾는 사전으로 변환하며, 원응답 목록은 그대로 보존합니다. CLI가 동적 키 사전 스키마를 거절하여 응답 버전을 v2로 변경했습니다.

|Fact 안의 항목|뜻|현재 형식|
|---|---|---|
|`id`|코드에서 fact(id)로 찾는 근거 이름입니다.|빈 문자열·중복 불가.|
|`span`|그 숫자가 context에 있는 시작·끝 위치입니다.|0 이상의 정수 두 개. 실제 원문과의 대응 검사는 후속 근거 검사입니다.|
|`text`|원문에서 가져온 숫자 표기입니다.|비어 있지 않은 문자열.|
|`value`|계산에서 사용할 수치 표현입니다.|비어 있지 않은 문자열. 값이 원문과 맞는지는 별도 검사입니다.|
|`unit`|이 값의 단위를 기록하는 자리입니다.|비어 있지 않은 문자열 또는 null. 단위 의미를 스키마가 알아서 판단하지 않습니다.|

`grounding`이 있다는 것은 설명이 제출됐다는 뜻입니다. 그 설명이 옳다는 판정은 아닙니다. `code`가 문자열로 제출돼 형식 검사를 통과했다고 해서 실행·정답 대조까지 통과한 것도 아닙니다.

## 다른 단계의 응답 내용

### 문장 수정 — RealizationResponse

`patches`는 원문의 어느 부분을 어떤 문장으로 바꿀지 담은 목록이며 최소 하나가 필요합니다. 각 수정에는 다음 항목이 모두 필요합니다.

|항목|뜻|
|---|---|
|`start`, `end`|원본 context의 수정 시작·끝 위치입니다.|
|`before`|바꾸기 전 문자열입니다. 삽입이면 빈 문자열일 수 있습니다.|
|`text`|새로 넣을 문자열입니다. 삭제이면 빈 문자열일 수 있습니다.|
|`element_ids`|이 수정이 표현하는 그래프 요소들의 번호입니다. 최소 하나가 필요합니다.|

Python은 시작이 끝보다 뒤인지 검사합니다. 실제 적용 단계에서는 범위·원문 일치·겹침·실제 변경 여부를 추가로 검사합니다.

### 독립 답변 — Observation / AnswerResponse

입력은 `context`, `question` 두 항목뿐입니다. 원천 정답·풀이·제작 유형을 추가하면 입력 검사에서 거절합니다. 응답은 `text` 하나에 자연어 답변을 담습니다. 특정 라벨이나 정답 개수를 응답 형식으로 요구하지 않습니다.

### 미리 만들어 둔 초안

아래 세 형식은 구조 초안입니다. 각 단계의 판단 규칙을 확정하기 전까지 실제 모델 호출에 사용하지 않도록 공통 호출 함수에서 막습니다.

|초안|주요 내용|
|---|---|
|`InverseResponse`|reviews 목록. 각 항목은 variable_id(대상 변수), state(복원 가능·불가·판단 불가), evidence(근거), proposed_path(제안 경로), reason(이유)입니다. 제안 경로 문자열이 있다고 검증된 실행 식이 되는 것은 아닙니다.|
|`SourceResponse`|source_annotations 한 개. 지정된 주장에만 side(A 또는 B), text(출처 문구), reason(이유)을 담습니다. Python 호출부가 지정된 쪽과 응답의 side가 같은지 검사합니다. 원래 충돌값과 그래프는 Python이 유지합니다.|
|`AuditResponse`|findings 목록. 각 항목은 criterion(검사 항목), judgment(통과·실패·판단 불가·해당 없음), reason(이유), evidence(근거)입니다. 이 judgment는 감사 의견이며 파이프라인 전체 실행 상태가 아닙니다.|

### 설명과 검사가 보장하는 범위

필드 이름·타입·필수 여부는 스키마에 정의돼 있습니다. 원천 정답 메타데이터의 일치, 중복 ID, 본문 위치 일치 등은 같은 Python 모듈의 추가 검사로 확인합니다. 이런 추가 검사 모두가 자동 생성 JSON Schema 안에 표현되는 것은 아니므로, **LLM이 JSON Schema에 맞춰 답했더라도 Python 검사를 생략하지 않습니다.**

## 스키마 검증 파일 — validation.py

스키마 폴더 안의 **[validation.py](validation.py)**가 공통 검사 파일입니다. 입력 준비 코드, 단계 실행 코드, 모델 응답 처리 코드가 이 파일을 사용합니다.

|함수|받는 것|하는 일과 결과|
|---|---|---|
|`parse_json`|JSON 원문|JSON을 읽습니다. 같은 항목 이름이 두 번 나오거나 유효하지 않은 숫자가 있으면 거절합니다.|
|`parse_json_object`|LLM의 JSON 응답 원문|위 검사에 더해 최상위가 객체인지 확인합니다.|
|`validate`|스키마 이름과 읽어 둔 데이터|필수 항목·타입·추가 항목·정의된 Python 조건을 검사합니다. 통과하면 입력 그대로 반환하고, 실패하면 오류를 발생시킵니다.|
|`check_json`|스키마 이름과 JSON 원문|검사 결과를 PASS/FAIL로 돌려줍니다. 실패하면 잘못된 항목 위치와 이유를 담습니다.|
|명령행 실행|스키마 이름과 파일 경로|파일을 수정하지 않고 검사 결과를 출력합니다. 통과는 종료 코드 0, 실패는 1입니다.|

### 실제 확인한 예

- 기존 첫 10건 입력 파일은 검사에 통과했습니다.
- 그 입력을 메모리에서만 복사하고, 첫 문제의 `reference_precision` 값을 정수 0에서 문자열 `"0"`으로 바꾸면 거절됩니다. 오류 위치는 첫 문제의 reference_precision이며 이유는 정수가 아니라는 것입니다. 원본 파일은 변경하지 않았습니다.
- 독립 답변의 `text`에 문자열 대신 숫자 42를 넣으면 거절됩니다. `text` 항목이 없거나 정의에 없는 항목을 추가해도 거절됩니다.

검사기는 문자열 `"0"`을 숫자 0으로 자동 수정하지 않습니다. 원응답을 보존하고 잘못된 필드와 이유를 남기는 것이 원칙입니다.

## 언제 전달하고 검사하는가

1. 호출 전에 역할에 맞는 응답 스키마를 가져옵니다. 없거나 비어 있거나 만들 수 없으면 FAIL을 기록하고 호출하지 않습니다. 등록하지 않은 새 역할도 검사를 우회하지 못합니다.
2. 모델 입력을 검사합니다. 독립 답변 입력에는 context와 question 두 항목만 허용합니다.
3. 모델을 호출할 때 프롬프트와 그 응답 스키마를 함께 전달합니다. 별도 요청 스키마를 모델에 보내는 요구는 없습니다. 기존 request 정의는 내부 입력에 허용하지 않은 필드가 섞이지 않도록 확인하는 용도입니다.
4. 응답을 받으면 원문을 먼저 기록하고 JSON 문법·필드·타입을 Python으로 검사합니다.
5. 통과한 응답만 다음 처리에 넘깁니다. 오류는 원응답·필드 위치와 함께 기록하고 자동 보정·재호출하지 않습니다.

호출 전후의 공통 함수는 [providers/structured.py](../providers/structured.py)입니다. CLI 연결 코드는 추가됐으나 내부 도구 차단 미검증으로 실제 모델 실행은 중단됩니다. 전달 방식은 native 또는 prompt를 명시해야 하며 실제 지원 여부는 통신 어댑터에서 확인해야 합니다. CLI 코드는 native 응답 스키마 인자를 사용합니다. 공통 함수는 요청 형식이 정해진 POT 작성과 독립 답변만 수용합니다. 문장화 요청의 입력 투영은 아직 미연결이고, 복원·출처·감사 응답의 세부 판단 계약은 초안이므로 이 공통 함수를 통한 실제 호출을 막습니다.

`RunContext.invoke`는 여섯 LLM 역할의 응답 스키마를 **처리 함수 호출 전에** 확인·저장하고 `response_schema` 인자로 전달합니다. Python 처리 함수 목록은 따로 명시하므로 스키마 삭제나 역할 이름 오타가 무검사 호출로 바뀌지 않습니다. 스키마 인자를 받지 않는 과거 함수에 인자를 빼고 재호출하지 않습니다. 단계 처리 함수가 잘못된 답변을 PASS로 돌려줘도 필드 검사를 통과하지 못하면 FAIL로 중단합니다. 이는 응답 형식 검사이며 의미 검증 완료를 뜻하지 않습니다.

### 호출 전후 코드 확인 결과

모델 통신은 `providers/structured.py`의 공통 경계에서 응답 스키마를 받은 `transport(...)`로 이어집니다. 이후 추가한 [CLI 코드](../providers/cli.py)의 `call()`도 이 경계를 사용하며 실제 프로세스 시작 전 내부 도구 차단 미검증 조건에서 중단합니다. 단계의 여섯 LLM 역할에도 같은 응답 정의를 적용합니다. 스키마 목록에서 이름이 사라져도 LLM 역할이라는 사실은 유지되도록 역할 목록을 분리했습니다.

- 스키마 누락·빈 정의·알 수 없는 역할·전달 방식 미지정은 호출 전에 실패 기록을 남깁니다.
- 단계 기록은 `03-result/schema-check.json`, `result.json`, 문제의 `events.jsonl`에서 실패 원인을 연결합니다. 공통 전달 함수는 호출별 `03-result/schema-check.json`에 통신 시작 여부를 남깁니다.
- 원응답이 있으면 먼저 보존하고 JSON 문법과 응답 필드·타입을 검사합니다. 오류를 자동 보정하거나 재호출하지 않습니다. 통신 자체가 실패해서 응답이 없으면 그 실패를 기록하며 검사 통과를 만들지 않습니다.
- 로컬 대역으로 여섯 역할의 스키마 삭제 시 실행 함수 호출 0회, 스키마 사전 저장·전달, 잘못된 응답 보존·거절을 확인했습니다. 기존 입력·준비·제어 검사를 포함해 39개가 통과했습니다. 실제 모델 호출 결과는 아닙니다.

초안 역할의 로컬 대역은 형식·흐름 검사에만 씁니다. 공통 전달 함수는 초안·입력 투영 미연결 역할의 실제 통신을 막습니다. 이후 CLI 연결을 추가할 때도 이 경계를 사용하고 내부에서 별도 호출을 만들면 스키마 전달·응답 검사를 함께 연결해야 합니다. CLI 내부의 숨은 요청까지 점검 완료했다는 뜻은 아닙니다.

## 입력 보존과 검증

원문 문단·표·셀·숫자 위치, 원천 출처, 정답 값·타입·자릿수, 배율·음수 부호를 검사합니다. 원문 위치와 해당 문자열, 정답 정밀도·음수 플래그의 일치도 Python에서 검사합니다. 금융적 의미나 질문의 반올림 지시를 이 스키마가 추정하지 않습니다.

기존 10·30·100건 입력과 해시는 다시 쓰지 않았습니다. 읽을 때 새 스키마를 적용합니다. 앞으로 새로 준비하는 묶음에는 스키마 이름·버전·해시가 manifest에 기록되며 일치하지 않는 버전은 거절합니다. 원천 파싱 사본은 보존 자료이며 별도 LLM 공통 입력으로 펼치지 않습니다.

POT의 code는 Python 소스 문자열입니다. 스키마에 사칙연산 제한을 넣지 않았습니다. 기존 제한 실행기 교체는 별도의 POT 실행 작업이며 이번에 교체 완료한 것이 아닙니다.

## 사용

프로젝트 전용 환경 `.venv`에 Pydantic 2.13.5를 설치했고 pyproject.toml에 의존성을 명시했습니다.

```sh
PYTHONPATH=src .venv/bin/python -m finarch.dataset.schemas.registry --output src/finarch/dataset/schemas/json
PYTHONPATH=src .venv/bin/python -m finarch.dataset.schemas.validation --schema prepared.input --input data/prepared/first-10/input.json
PYTHONPATH=src .venv/bin/python -m unittest finarch.dataset.checks.test_schemas finarch.dataset.checks.test_preparation finarch.dataset.checks.test_pipeline -q
```

방식 근거: [Pydantic JSON Schema 생성](https://docs.pydantic.dev/latest/concepts/json_schema/), [엄격한 타입 검사](https://docs.pydantic.dev/latest/concepts/strict_mode/). fin-astra는 읽기 전용으로 참고했고 기존 스키마 코드를 복사하지 않았습니다.


## 출처 계획 스키마

`source_plan.py`가 원정의이며 `json/02-generation.01-perturbation.ic-source-plan.schema.json`은 그 정의를 내보낸 파일입니다. `SourcePlan.model_validate(..., strict=True)`로 검사합니다. LLM 응답 스키마가 아니라 13번의 로컬 제작 계획 형식입니다.

- `base_plan_ref`, `base_plan_sha256`: 고정한 A/B 값·계산 그래프의 기준 파일과 해시.
- `sources`: A/B 각각의 출처 ID·역할·정보 접근·직접/간접 전달·검증 상태.
- `intended_reliability`, `source_condition`: private 제작 조건이며 최종 본문에 그대로 노출하지 않습니다.
- `claim_order`: 이번 family의 고정 A/B 순서.
- `realization_rules`: 두 값 보존, 출처 귀속, 정정·추가 수익 오독 방지 등 문장화 조건.
- `provenance`, `semantic_status`, `final_text_status`: 제작한 출처 조건임과 아직 의미/문장 검사가 끝나지 않았음을 명시.

문장 생성용 `realization-input.json`에는 원문 위치와 인용, 해당 Python 코드 줄, 그래프 노드, A/B 값 및 출처를 함께 넣습니다. 별도 요청 스키마를 LLM에 주라는 의미가 아닙니다. 실제 문장 생성 응답은 기존 `dtt.realize.response`의 patches 형식이며, 호출과 응답 검증은 다음 단계의 미실행 작업입니다.

현재 source.plan은 A_ONLY/B_ONLY만 허용하고 sources는 정확히 한 개입니다. 반대쪽 출처는 누락시키며 낮은 신뢰도로 대체하지 않습니다. 이전 네 후보 파일은 이력입니다.

## 16번 현재 연결

`llm.py::RealizationRequest`는 전송할 C/Q·Python 코드·DAG 구조·허용 편집 슬롯을 내부에서 검사합니다. 이 요청 스키마는 LLM에 보내지 않습니다. `RealizationResponse`의 `patches` 스키마는 전용 프롬프트와 함께 Codex CLI에 전달하고, 원응답 보존 후 동일 정의로 검증합니다. 원문 위치·ID·허용 숫자·EA 최소 삭제의 추가 검사는 `program/dtt_realize.py::check_response`가 담당합니다. 스키마 PASS는 의미 PASS가 아닙니다. 현재 실제 기록은 [16번 안내](../../../reports/run/first-10-pot-validated-v3/test-0001/05-text/STAGE16-README.md)를 따릅니다.


## 17번 의미 검사 응답

`dtt.audit.response` v2는 `findings`의 8개 항목(보존·변경·범위·출처·계획 밖 표현·문법·정정/해소·EA 일관성)과 `observed_state`, 이유, 인용을 받습니다. 인용은 실제 원문/최종 본문/질문의 문자열이며 Python이 대조합니다. 항목 누락·중복·적용 범위 오류·거짓 인용은 통과시키지 않습니다. 의미 판정 불가와 형식 오류는 별도입니다.

내부 `AuditRequest`는 원본·최종 C/Q, 변경 의도, 편집 목록, 역산 보류를 검사합니다. 별도 요청 스키마를 모델에 보내지는 않습니다. 과거 실행의 응답 정의는 당시 저장본을 유지합니다.

## 단계별 스키마 JSON 파일 이름

2026-09-15 적용. `src/finarch/dataset/schemas/json/`의 파일명은 **소속 단계.작업.요청 또는 응답.schema.json**으로 지정합니다. `index.json`은 등록 스키마 ID와 실제 파일명을 연결합니다. 내부 ID·버전·JSON 내용·해시는 이름 변경만으로 바꾸지 않습니다. 자동 내보내기도 `registry.py`의 `SCHEMA_FILES`를 사용합니다.

원본 검토와 생성문 검증은 같은 정의를 사용하므로 `shared.01-02.02-03.review-and-validation`으로 표시합니다. 각각 Preparation `02-review-and-correct`, Generation `03-validation`에서 사용합니다. `source.plan`은 별도 Python 로컬 계획 정의로 LLM 응답 등록부에는 포함하지 않습니다.

| 내부 ID | JSON 파일명 |
|---|---|
| `preparation.revise.request` | `01-preparation.02-review-and-correct.revision.request.schema.json` |
| `preparation.revise.response` | `01-preparation.02-review-and-correct.revision.response.schema.json` |
| `preparation.evidence.request` | `01-preparation.03-calculation.review-answer-evidence.request.schema.json` |
| `preparation.evidence.response` | `01-preparation.03-calculation.review-answer-evidence.response.schema.json` |
| `dtt.feedback.request` | `02-generation.feedback.case-feedback.request.schema.json` |
| `dtt.feedback.response` | `02-generation.feedback.case-feedback.response.schema.json` |
| `prepared.input` | `01-preparation.01-source.prepared-input.schema.json` |
| `pot.author.request` | `01-preparation.03-calculation.pot.request.schema.json` |
| `pot.author.response` | `01-preparation.03-calculation.pot.response.schema.json` |
| `dtt.realize.response` | `02-generation.02-generate-text.realization.response.schema.json` |
| `dtt.realize.request` | `02-generation.02-generate-text.realization.request.schema.json` |
| `dtt.audit.request` | `shared.01-02.02-03.review-and-validation.request.schema.json` |
| `dtt.audit.response` | `shared.01-02.02-03.review-and-validation.response.schema.json` |
| `dtt.audit.response.v2` | `shared.01-02.02-03.review-and-validation.response.v2.schema.json` |
| `source.plan` (로컬 계획) | `02-generation.01-perturbation.ic-source-plan.schema.json` |

읽는 순서: 이 대응표 → schemas/README.md → json/index.json → 해당 JSON → Python 원정의. Viewer의 현재 스키마 조회는 이 대응표와 같은 파일 경로를 표시하며 과거 호출에 저장된 스키마는 그대로 보존합니다.

### 미사용 정의 제거 및 공용 사용 위치

현재 스키마 JSON과 자동 내보내기 등록부에서 역산 초안, 독립 답변 요청·응답, 미연결 출처 문구 초안 4개를 제거했습니다. 과거 실행에 저장된 스키마·응답은 변경하지 않습니다. 제거된 역할을 호출하면 응답 스키마 누락으로 호출 전에 차단됩니다.

공용 파일명은 `shared.01-02.02-03.review-and-validation.{request,response}.schema.json`입니다.
- `01-02`: `01-preparation/02-review-and-correct`의 원본 검토·보정.
- `02-03`: `02-generation/03-validation`의 생성문 검증.
- `response.v2`는 과거 응답 검사에 사용하므로 유지하며 신규 호출용은 아닙니다.

현재 JSON은 로컬 source plan을 포함해 15개입니다. 앞서 기록한 19개는 제거 전 수량입니다.

## Human-review 실패 해석

`shared.01-07.02-05.failure-interpretation`과 `shared.01-07.02-05.display-translation`의 request/response JSON을 `json/`에서 확인합니다. 전자는 증거에 연결된 영어 의견, 후자는 표시용 번역이며 production verdict/feedback과 구별합니다.

## QI05 품질 범위 sidecar

[quality_scope.py](quality_scope.py)는 오프라인 보고서 전용이며 LLM request/response registry와 분리합니다. 생성 시 `QualityReport.model_json_schema()`로 [실제 sidecar-schema.json](../../../../reports/run/20260916-quality-v1/sidecar-schema.json)을 내보냅니다. 버전·enum·필수 필드·SHA256 형식·중복 ID·분모를 검사하며, 실제 입력 해시는 adapter에서 재확인합니다. 독립 검토 NOT_REVIEWED는 선택한 근거에서 별도 검토 기록을 가져오지 않았다는 의미입니다.

QI06 `response_screen.py`는 저장용 `response-screen-v2` sidecar 계약입니다. 실제 export는 [review-v2/sidecar-schema.json](../../../../reports/run/20260916-review-v2/sidecar-schema.json), 보고서는 [response_screen.json](../../../../reports/run/20260916-review-v2/response_screen.json)입니다. LLM response schema와 별개입니다.

QI02 `original_baseline.py`의 public allowlist는 [public-input-schema.json](../../../../reports/run/20260916-original-baseline-v1/public-input-schema.json), private 보고서 계약은 [sidecar-schema.json](../../../../reports/run/20260916-original-baseline-v1/sidecar-schema.json)으로 export됩니다. 실제 모델용 요청은 public Q/C만 포함하며 private 보고서가 아닙니다.

QI03 `source_pair_review.py`의 실제 저장 보고서 계약은 [source-pairs-v1/sidecar-schema.json](../../../../reports/run/20260916-source-pairs-v1/sidecar-schema.json)입니다. [pair_manifest.json](../../../../reports/run/20260916-source-pairs-v1/pair_manifest.json)의 정확 연결·제외 이유·양쪽 상태를 검증하며 LLM 응답 계약을 바꾸지 않습니다.
