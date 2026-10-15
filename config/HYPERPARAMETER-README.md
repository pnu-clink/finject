# 실행 설정 읽는 순서

`hyperparameter.json` → `codex-profiles.toml` → 실행 폴더의 `config.json` 순서로 확인합니다.

Preparation·Generation·Evaluation·Analysis 모두 `schedule`은 대상·실행 수, `run`은 모델 선택·실험 조건을 담습니다. 실제 모델명·추론 강도·API 출력 한도는 프로필 한 곳에서 정의합니다. 단가·가격 확인 날짜·키 경로·청구 설명·과거 실행 이력은 hyperparameter에 넣지 않습니다.

|설정|무엇을 정하는가|읽는 코드|
|---|---|---|
|preparation.schedule / run|사전 준비 대상·동시 실행·역할별 모델|dataset의 schedule_settings.py|
|generation.schedule / run|변형 생성·보완·검증 모델과 동시 실행|dataset의 schedule_settings.py|
|generation.run.models.ea_inverse_review|EA 역산 전용 `sol61-high-api` 선택: gpt-6.1-sol / high, 출력 32,768·총 한도 500,000|profiles.py → ea_inverse_review.py → Responses API|
|evaluation.schedule.dataset|dataset run·원천 입력·원본 수·7변형 통과 조건|experiments의 settings.py → dataset.py|
|evaluation.run.models|모델별 OFF/ON 프로필|settings.py → pipeline.py|
|evaluation.run.transport / cache|Batch 호출 / 캐시 OFF|openai_batch.py / openai_api.py|
|evaluation.run.seed / definition_source_run|요청 순서 seed / 사용할 prompt·schema의 기존 run|pipeline.py|
|analysis.run.backend|`codex` 또는 `api` 선택|settings.py → 02_analysis/pipeline.py|
|analysis.run.models|Codex 프로필과 API 프로필|settings.py → 02_analysis/llm_backend.py|
|analysis.schedule / run.technical_retry_limit|동시 실행·제한 시간 / 기술적 실패 재시도 횟수|02_analysis/llm_backend.py|

Analysis는 `concurrency=100`, `adaptive.enabled=false`로 고정합니다. CPU 표본은 기록하지만 한도를 늘리지 않습니다. experiments pipeline의 기본 설정이 이 JSON이며, 과거 TOML은 명시적으로 선택할 때만 읽습니다. 기존 run은 동결 설정을 읽으므로 모델 변경 시 `restart-analysis`로 이전 기록을 보존해야 합니다.

## 현재 선택

|용도|프로필|모델·추론|출력 한도|
|---|---|---|---:|
|Evaluation · Reasoning OFF|luna6-none-api|gpt-6-luna · none|65,536|
|Evaluation · Reasoning ON|luna6-medium-api|gpt-6-luna · medium|65,536|
|Analysis · 현재 Codex|sol61-low-cli|gpt-6.1-sol · low|CLI에서 이 API 옵션을 적용하지 않음|
|Analysis · API 선택 시|sol61-low-api|gpt-6.1-sol · low|65,536|

분석 방식을 바꾸려면 `analysis.run.backend`만 `api` 또는 `codex`로 바꾼 뒤 새 실행을 준비합니다. Codex 오류가 나도 API로 자동 전환하지 않습니다. 풀이에는 public의 Q/C·precision만 전송하고, private는 E04 수치 평가와 A01 이후 분석에서 사용합니다.

원본과 변형 모두 **Unguided Solving / Criteria-Guided Solving × Reasoning OFF/ON**으로 실행합니다. 이 두 풀이 지시는 고정된 실험 구조이며 hyperparameter에 별도 선택 항목을 두지 않습니다. 실제 요청 manifest에는 `prompt_condition: unguided` 또는 `guided`로 기록합니다. 모델당 10원본·70변형은 320요청, 100원본·700변형은 3,200요청입니다. 과거 실행은 당시 저장된 요청과 건수를 유지합니다.

`max_output_tokens`는 출력 상한이며 그만큼 생성하도록 강제하는 값이 아닙니다. OpenAI 요청에는 `thinking_budget`을 보내지 않습니다. Reasoning OFF/ON은 프로필의 `effort`로 지정합니다.

## 길이 조정의 근거와 적용 시점

저장된 야간 요청의 실제 값은 다음과 같습니다.

|실행 자료|최초 → 재시도 출력 한도|관찰|
|---|---|---|
|exp-001 문항 분석 800건|12,000 → 32,768|잘림 203건; 재시도 233건 중 잘림 12건 남음|
|exp-001~003 응답 분석|32,768 → 65,536|재시도는 형식·인용 오류를 포함하며 길이 증가만으로 모두 해결되지는 않음|
|exp-001~003 Luna 풀이|8,192|저장된 풀이 총 9,000건에서 OUTPUT_TRUNCATED 없음|
|exp-004 Luna 풀이|8,192|300건 반환·형식 통과; 변경 전 동결된 실행|

이번 설정은 새 요청부터 65,536을 사용합니다. 기존 run의 설정·manifest·원응답을 소급 수정하지 않습니다. API 분석 상한과 Codex 분석의 실제 실행 옵션은 같다고 표시하지 않습니다.

## 실행과 확인

- 기본 설정 확인: `PYTHONPATH=src .venv/bin/python -u -B -m finarch.experiments.pipeline config`
- 첫 Analysis 설정 동결: `pipeline configure-analysis --run <run> --config config/hyperparameter.json`
- Analysis 실행: `pipeline analysis --run <run>` (앞의 Python 진입점에 command를 붙입니다).
- 중지된 Analysis의 모델 변경: `pipeline restart-analysis --run <run> --config config/hyperparameter.json --authorization '<실제 사용자 지시>'` 후 `analysis`를 실행합니다. 이전 분석은 `02_analysis-history`에 보존하며 Evaluation은 재호출하지 않습니다.
- 실행 당시 설정: `02_analysis/config.json`; 실제 모델·effort·명령: 단계별 `calls/*/attempt-*/provider-request.json`.
- 실제 진행과 CPU 표본: `02_analysis/scheduler.json`; 실행 명령과 처리 현황: `pipeline.log`와 `events.jsonl`.
- Evaluation의 데이터 경로는 실행 전에 별도 확인합니다. 아래 557원본은 남아 있는 과거 Evaluation 선택값이며 현재 TAT-QA 291원본 실행의 동결 입력과 다릅니다.

[실험 전체 흐름](../docs/02-experiments/README.md) · [프로필](codex-profiles.toml) · [설정](hyperparameter.json)

현재 `evaluation.run.definition_source_run`은 null입니다. 다음 새 준비는 [실험 단계별 프롬프트](../src/finarch/experiments/prompts/README.md)에서 공통·Unguided·Criteria-Guided 지시를, [단계별 스키마](../src/finarch/experiments/schemas/json/README.md)에서 공통 응답 형식을 읽어 run에 동결합니다. 기존 run을 재개하면 저장 당시의 정의를 사용합니다.

이 공통 파일에 남아 있는 과거 Evaluation 선택값은 20260917-003의 557원본·3,899변형이며 17,824요청입니다. 다음 20260917-002의 1,080원본은 별도 run에서 동일 조건을 유지합니다. 실행 당시 설정은 각 run의 config에 고정합니다.
