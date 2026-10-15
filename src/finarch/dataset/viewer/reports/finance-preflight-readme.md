# FinanceReasoning 전체 Preparation 실행 전 정리

원천 {total}건 → 빈 본문 {empty_context}건 제외 → boolean 정답 {boolean_answer}건 제외 → Q·C 완전 중복 {duplicate_qc}건 제외 → **{selected}건**. 빈 본문에는 공백과 JSON 빈 배열·객체·문자열, null이 포함됩니다.
이번 결과는 입력 준비와 로컬 코드 검사입니다. 새 POT·검토 API를 호출하지 않았으며 이전 LLM 응답을 재사용하지 않았습니다.

|원천|전체|본문 없음|boolean|Q·C 중복|최종|
|---|---:|---:|---:|---:|---:|
{count_rows}

## 중복 제거

질문과 본문을 정확한 문자열로 비교했습니다. 같은 본문에 질문이 다르면 유지합니다. easy → medium → hard 및 원본 순서상 먼저 나온 한 건을 남겼고, 아래 여섯 쌍은 정답도 같습니다. ID는 **원본 ID**이며 실행 ID 대응은 selection-manifest.json에 있습니다.

|남긴 원본|제외한 원본|정답|
|---|---|---|
{duplicate_rows}

원천 파일은 보존했습니다. 제외는 새 실행용 input.json에만 반영했습니다.

## Python 구문 조사

대상은 최종 {selected}건의 **원본 python_solution**입니다. AST로 읽었고 원본 프로그램은 실행하지 않았습니다. 새 POT의 실패 건수를 측정한 것이 아닙니다.

|그래프와 대조할 구문|문항 수|
|---|---:|
{syntax_rows}

유형 간 중복을 제외하면 **{union}건**입니다. 함수 하나로 감싼 원본 풀이와 표 인덱싱은 별도 구조 통계로만 기록했습니다. 블록 if와 달리 `a if condition else b`는 현재 그래프가 지원합니다. 새 POT이 다른 표현으로 작성할 수 있으므로 이 건들을 자동 제외하지 않습니다. 이번에는 구문 지원을 확대하거나 POT 프롬프트를 변경하지 않았습니다.

## 스케줄과 충돌 확인

- API: shared.api.concurrency=200을 단일 기준으로 사용합니다. API만 사용하는 Preparation/Generation은 CPU와 무관하게 최대 200문항으로 고정합니다. 남은 대상이 적으면 그 수만 실행합니다.
- 같은 프로세스의 중첩 Generation 작업과 토큰 계수 요청에도 HTTP 요청 상한 200을 적용합니다. 여러 독립 프로세스·서버 전체를 합산한 제한은 아닙니다.
- 같은 run은 schedule.lock으로 한 스케줄러만 소유합니다. 사망한 프로세스의 OS 잠금은 해제됩니다.
- 문항별 산출물은 각 worker 전용 경로에 저장합니다. queue·summary·review-gate는 스케줄러가 기록합니다. 공통 로그는 기존 잠금과 순번 처리를 유지합니다.
- 로컬 검사에서 200개 동시 worker로 250건을 처리하여 개별 파일, 공통 로그 250줄·순번, 주 스레드의 집계 기록을 확인했습니다. 실제 API의 429·네트워크 안정성 검사는 아닙니다.

## 중단 후 재개

`01-preparation/schedule-state.json`에 pending_ids / running_ids / completed_ids를 스케줄러만 기록합니다. 재개 기본 대상은 미완료 ID입니다. `--cases` 또는 `--cases-file`로 ID를 지정할 수도 있습니다.

재개 대상의 이전 폴더는 `restart-history/NNN-preparation/test-xxxx`로 이동해 보존합니다. 그 뒤 같은 문항 번호의 01-round / 01-source부터 다시 처리합니다. 이전 코드·응답·피드백을 이어 쓰지 않습니다. 완료된 다른 문항은 유지합니다. 정상 수행 중인 2·3차의 오류 피드백 반복은 기존 방식입니다.

```bash
# 이번 입력 정리·AST 조사에 사용한 명령
PYTHONPATH=src .venv/bin/python -m finarch.dataset.00-input.full_finance --catalog data/prepared/finance-reasoning/source-catalog.json --output '{input_directory}'

# API 호출 없는 실행 계획 확인
PYTHONPATH=src .venv/bin/python -m finarch.dataset.01-preparation.prepare_schedule --input '{input_directory}/input.json' --plan-only

# 이후 실제 실행 시 사용 (이번 작업에서는 실행하지 않음)
PYTHONPATH=src .venv/bin/python -m finarch.dataset.01-preparation.prepare_schedule --input '{input_directory}/input.json'

# 중단된 실행의 미완료 문항 ID를 다시 등록
PYTHONPATH=src .venv/bin/python -m finarch.dataset.01-preparation.prepare_schedule --run reports/run/RUN_ID --resume

# 특정 문항만 처음부터 재처리
PYTHONPATH=src .venv/bin/python -m finarch.dataset.01-preparation.prepare_schedule --run reports/run/RUN_ID --resume --cases test-0002 test-0010
```

## 파일과 읽는 순서

입력 폴더: `{input_directory}`

1. 이 README: 개수·중복·구문·변경 방식 요약.
2. finance-preflight.json: 공통 뷰어가 읽는 조사 결과와 근거 해시.
3. 입력 폴더 selection-log.json: 모든 제외 ID·이유·중복 대표 ID.
4. 입력 폴더 code-syntax-audit.json: 구문별 문항 ID와 미지원 호출 이름.
5. checks.log: 이번 로컬 검사 실행 결과.

공통 viewer에서 `{run_id}`를 선택하면 같은 내용을 보고 구문별 문항 ID를 펼칠 수 있습니다.
