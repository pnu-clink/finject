# Analysis 프롬프트 · 입력만으로 이해하도록 정리

[소스 안내](../../../../src/finarch/experiments/02-analysis/README.md) · [작업 기록](../README.md) · [공통 뷰어](http://127.0.0.1:8893/?run=20260927-experiment-source-layout&doc=reports%2Frun%2F20260927-experiment-source-layout%2Fprompt-clarity%2FREADME.md)

모델은 현재 요청의 프롬프트·데이터·응답 스키마를 받습니다. 다른 대화나 프로젝트 문서를 읽었다고 가정하지 않도록 내부 단계 번호를 실제 작업과 필드 설명으로 바꿨습니다. Codex와 API가 같은 설명을 사용합니다.

## 무엇을 바꿨는지

|기존 표현 또는 생략|현재 설명|
|---|---|
|`E04 numeric comparison`|`numeric_comparison.matches`: 저장된 기준 답과 원본 응답의 숫자를 기존 규칙으로 비교한 결과. 설명의 타당성이나 의미 정답 판정과 구별|
|`original_result`의 연결 관계 생략|원본의 MATCH/MISMATCH/UNEVALUATED와 변형의 NOT_ORIGINAL을 구별. 변형을 묶을 때 같은 모델·풀이 지시·추론 설정의 원본 행에 연결|
|`D02` 후속 논의 번호|출처 표기와 주장 위치의 영향을 구분하기 위한 후속 비교. 아직 실행되지 않은 토의 제안임을 명시|
|조건·문항 유형 코드|Unguided/Criteria-Guided, Reasoning OFF/ON, 원본과 일곱 변형의 실제 뜻·부모 관계를 설명|
|형식 통과와 숫자 후보|VALID는 형식 통과, A/B는 기준·대안 숫자와의 일치, FRONT/BACK은 주장 위치로 설명|
|연구 해석 집계와 분할 입력|전체·조건별·원본 결과별·대응쌍 집계의 뜻과 분모를 설명. 여러 입력 묶음에 반복되는 집계를 중복 합산하지 않도록 명시|

## 파일 역할과 읽는 순서

|순서|파일|확인 내용|
|---|---|---|
|1|[비교 분석에 전달할 전체 프롬프트](comparison-current.md)|공통 설명과 비교 분석 지시를 합친 실제 현재 문자열|
|2|[연구 해석에 전달할 전체 프롬프트](research-current.md)|공통 설명과 집계·해석 지시를 합친 실제 현재 문자열|
|3|[공통 설명](common-current.md)|두 요청이 공유하는 조건·변형 정의와 분석 범위|
|4|[이전 비교 프롬프트](comparison-before.md) · [이전 연구 프롬프트](research-before.md) · [이전 공통 설명](common-before.md)|수정 직전 원문|
|5|[로컬 확인 결과](validation.json) · [검사 로그](local-checks.log)|프롬프트 확인, 기존 로컬 검사, 실행 보류 상태|
|6|[작업 로그](../events.jsonl)|수정·검사·화면 확인 이력|

현재 원문은 [pipeline.py](../../../../src/finarch/experiments/02-analysis/pipeline.py)와 [llm_backend.py](../../../../src/finarch/experiments/02-analysis/llm_backend.py)의 문자열을 그대로 저장했습니다. 실행을 재개할 때 새 분석 요청은 이 문자열과 스키마를 사용합니다. 이미 동결된 요청은 변경 검사를 거치며 과거 원문을 덮어쓰지 않습니다.

이번 확인은 로컬 코드·문서 확인입니다. 실제 분석 모델의 이해도나 응답 품질을 검증한 결과는 아닙니다. 모델 호출·배치 제출 없이 Haiku와 Analysis의 실행 보류 상태를 유지합니다.

이 README는 `src/finarch/documentation/templates/experiment-analysis-prompt-clarity.md`에서 생성합니다.
