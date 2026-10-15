# 실험 설정 · hyperparameter.json

[소스 전체](../../src/finarch/experiments/README.md) · [Analysis 절차](../../docs/02-experiments/02_analysis/README.md) · [기본 설정](../hyperparameter.json) · [공통 모델 프로필](../codex-profiles.toml)

예를 들어 같은 저장 응답을 Codex로 분석하려면 `analysis.run.backend = "codex"`, API로 분석하려면 `"api"`로 정합니다. 두 방식 모두 A01 결과 취합 → A02 관계 비교 → A03 연구 해석을 사용하며, prompt와 응답 schema, 결과 검사 기준을 공유합니다.

명시적으로 선택하는 TAT-QA TOML 예시의 입력은 `generated_path="data/generated/20261003-003"`, `count=291`입니다. 새 TOML 준비는 generated를 필수로 요구하며 제작 run·results_path·input_path를 사용하지 않습니다. 717원문 중 기존 7종 자동 PASS·거절 없음 기준의 291문항군을 선정합니다. 모델과 네 조건은 유지하며 총 9,312요청을 준비합니다. Analysis용 메타정보 누락은 selection.json에 표시하며 임의로 채우지 않습니다.

TAT-QA Gemini 2.5 Flash는 [tatqa-gemini2.5-flash-thinking-1024.json](tatqa-gemini2.5-flash-thinking-1024.json)의 제공자 설정을 사용합니다. Native Gemini Batch, OFF `thinkingBudget=0`, ON `1024`, 최대 출력 `8192`로 준비합니다. Luna의 동결 prompt·schema를 재사용하며 응답은 새로 요청합니다. 현재 Gemini Developer API의 암묵적 캐시 비활성화가 확인되지 않아 캐시 금지 정책에서는 전송 전에 `CACHE_POLICY_BLOCKED`로 중단합니다. 준비 완료를 제출 완료로 표시하지 않습니다.

```bash
PYTHONPATH=src .venv/bin/python -u -B -m finarch.experiments.pipeline prepare --config config/experiments/tatqa-gemini2.5-flash-thinking-1024.json
```

같은 준비 명령을 반복하면 새 실험을 만듭니다. 준비된 run을 계속할 때는 해당 `--run`을 사용합니다. 모델 호출 전에 캐시 정책과 전송 상태를 확인합니다.

2026-10-03 사용자는 `20261003-exp-006-tatqa-gemini-2-5-flash`에 한해 비활성화가 불가능한 암묵적 캐시를 허용했습니다. 상위 `pipeline.py authorize-gemini-cache --run <run> --model-key gemini-2.5-flash-batch --authorization '<실제 사용자 승인>'`으로 기록한 후 `run --evaluation-only --run <run>`을 실행합니다. 승인 기록은 `cache-exceptions.json`이며 기존 동결 config·요청·금지 정책은 보존합니다. 다른 run에 이 승인을 복사하지 않습니다. 명시적 캐시와 다른 run의 응답 재사용은 금지하며, 캐시 쓰기 사용량 누락은 0이 아니라 미확인으로 남깁니다. `GEMINI_BATCH_PROGRESS` 로그에는 실제 Batch name·제공자 상태·반환된 batchStats를 표시합니다.

이 2.5 제출은 Google의 신규 사용자 모델 접근 제한으로 HTTP 404 `BATCH_REJECTED`입니다. Batch ID·생성 응답은 없습니다. 사용자 선택에 따라 [tatqa-gemini3.8-flash-medium.json](tatqa-gemini3.8-flash-medium.json)으로 별도 준비합니다. Gemini 3.8은 완전한 추론 OFF와 minimal을 지원하지 않으므로 Unguided/Guided × ON `thinkingLevel=medium` 두 조건만 생성합니다. 291 × 8 × 2 = 4,656요청이며 low를 OFF로 치환하지 않습니다. [공식 추론 설정](https://ai.google.dev/gemini-api/docs/generate-content/thinking)과 [Batch 단가](https://ai.google.dev/gemini-api/docs/pricing#gemini-3.8-flash)를 기준으로 입력 $0.375/M·출력(추론 포함) $1.875/M을 사용합니다. 이 단가는 2026-12-31까지의 소개 가격입니다. 준비는 실제 제출이 아닙니다.

```sh
PYTHONPATH=src .venv/bin/python -u -B -m finarch.experiments.pipeline prepare --config config/experiments/tatqa-gemini3.8-flash-medium.json
```

사용자는 비용 때문에 3.8 Flash 준비를 중지하고 텍스트용 [tatqa-gemini3.5-flash-lite-medium.json](tatqa-gemini3.5-flash-lite-medium.json)을 선택했습니다. `gemini-3.8-flash-lite`는 API 모델 조회에서 404이며, 확인된 3.8 Lite TTS는 음성 합성용입니다. Lite 실험은 `gemini-3.5-flash-lite`, Native Batch, Unguided/Guided × ON `thinkingLevel=medium`, 4,656요청, 출력 상한 8,192로 준비합니다. Batch 단가는 입력 $0.15/M·추론 포함 출력 $1.25/M입니다. 입력 문자 수/4 추정과 요청당 전체 출력 1,000토큰 가정에서 약 $6.93이며 실제 청구액이 아닙니다. 기존 3.8 동결 자료는 보존하고 pipeline의 pause로 미제출 상태를 유지합니다.

```sh
PYTHONPATH=src .venv/bin/python -u -B -m finarch.experiments.pipeline prepare --config config/experiments/tatqa-gemini3.5-flash-lite-medium.json
```

1,080원본 Luna 실행은 [luna-1080.toml](luna-1080.toml)을 사용합니다. `20260917-002`의 검증된 원본 외부사용 분류를 요구하고 private에만 동결합니다. 풀이 모델 입력은 기존 Luna와 같은 prompt·schema의 Q/C·precision입니다. `run_label = "luna"`는 새 실행 폴더의 모델 접미사입니다.

## 읽는 순서

## 현재 기본 설정과 실제 읽는 순서

1. `config/hyperparameter.json`: 대상·동시 수·backend·프로필 이름을 선택합니다. `--config`를 생략한 experiments pipeline의 기본 파일입니다.
2. `config/codex-profiles.toml`: 선택한 프로필의 실제 모델명·effort·CLI 인자·API 출력 한도를 해석합니다.
3. `<run>/02_analysis/config.json`: 해석한 설정과 출처 해시를 실행 전에 동결한 기록입니다. 재개는 이 기록을 읽어 이미 시작한 요청의 모델이 바뀌지 않게 합니다.
4. `<run>/02_analysis/runtime-schedule.json`: `configure-schedule`로 설정한 경우 동시 수·시간 제한만 덮어씁니다. 모델·effort는 변경하지 않습니다.

현재 Analysis는 `backend="codex"`, `models.codex="sol61-low-cli"`, **gpt-6.1-sol / low · 동시 100건 고정**입니다. `adaptive.enabled=false`라서 CPU가 낮아도 증설하지 않습니다. CPU 표본은 60초마다 기록하고 측정 실패는 미확인으로 남깁니다. API 선택용 `sol61-low-api`는 같은 모델·effort이며 자동 전환하지 않습니다.

`config/experiments/*.toml`은 명시적 과거/모델별 Evaluation 설정입니다. 해당 파일을 `--config`에 지정하면 그 파일의 프로필과 설정을 읽는 호환 경로입니다. 새 Analysis의 공통 기준으로 모델을 중복 편집하지 않습니다. 이 문서의 TAT-QA Evaluation 예시와 기존 run의 설정은 보존합니다.

## 설정 확인 → 동결 → 실행

```sh
PYTHONPATH=src .venv/bin/python -u -B -m finarch.experiments.pipeline config
PYTHONPATH=src .venv/bin/python -u -B -m finarch.experiments.pipeline configure-analysis --run <run> --config config/hyperparameter.json
PYTHONPATH=src .venv/bin/python -u -B -m finarch.experiments.pipeline analysis --run <run>
```

앞 두 명령은 모델을 호출하지 않습니다. `configure-analysis`는 첫 요청 전의 설정만 동결합니다. `analysis`가 A01 → A02 → A03을 실행하며 중지된 run은 실행하지 않습니다. Evaluation 재호출은 없습니다.

이미 실행한 분석의 모델을 바꾸려면 먼저 `pause`한 뒤 아래 명령을 사용합니다.

```sh
PYTHONPATH=src .venv/bin/python -u -B -m finarch.experiments.pipeline restart-analysis --run <run> --config config/hyperparameter.json --authorization '<사용자의 실제 모델 변경 지시>'
PYTHONPATH=src .venv/bin/python -u -B -m finarch.experiments.pipeline analysis --run <run>
```

`restart-analysis`는 Evaluation 완료와 해당 프로세스 종료를 확인하고 이전 분석 전체를 `02_analysis-history/<시각>`에 보존합니다. 이전 입력·prompt·schema를 유지한 새 모델의 요청을 준비하며 기존 판정을 재사용하지 않습니다. 이 준비 명령의 모델 호출은 0건입니다. 다음 `analysis`부터 새 모델을 호출합니다. 원 Evaluation 설정·응답·점수는 보존합니다.

동시 수만 바꿀 때는 `configure-schedule --run <run> --config config/hyperparameter.json`을 사용합니다. `scheduler.json`에는 실제 한도·실행·대기 건수·CPU 표본이, `events.jsonl`과 `pipeline.log`에는 실제 Python 명령과 진행 이력이 기록됩니다. 첫 제공자 확인 호출 중에는 실행 1건으로 표시되며 통과 후 최대 100건을 실행합니다. 제공자 처리 시간·계정 한도를 CPU로 추정하지 않습니다.

승인된 여러 run은 `analysis-sequence --run <첫 run> --analysis-run <다음 run>`으로 Analysis만 순서대로 처리합니다. 오류·미확인 전송은 원기록을 보존하고 중단하며 Evaluation이나 다른 모델로 자동 전환하지 않습니다.

이 README는 `src/finarch/documentation/templates/experiment-config.md`에서 생성합니다.

## 모델 비교를 위한 별도 Analysis

동일 Evaluation을 다른 분석 모델로 처음부터 해석할 때는 기존 run을 덮어쓰지 않고 `prepare-analysis-variant --source-run <원본> --run <원본-sol-low> --analysis-tag sol-low --config config/hyperparameter.json --authorization '<실제 지시>'`로 별도 run을 만듭니다. Evaluation 파일만 동일 복사하며 이전 분석 판정은 가져오지 않습니다. 이후 `analysis --run <새 run>`이 A01부터 진행합니다. `TASK_START`는 실행 전에 실제 모델·effort·태그·작업·요청 수·동시 수를 출력합니다.
