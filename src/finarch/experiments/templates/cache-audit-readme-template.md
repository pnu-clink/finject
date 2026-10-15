# {run_id}: 캐시 검사와 재실행 상태

**캐시 차단 기능 미확인으로 실제 모델 호출은 0건입니다.** 같은 100원문·700변형을 이용하는 3,000요청(실험 1: 200, 실험 2: 2,800)을 준비했지만 캐시 없는 재실행을 완료한 상태가 아닙니다.

## 왜 호출하지 않았는가

설치된 Codex CLI 0.155.0의 도움말·app-server 생성 스키마와 공식 config 스키마에서 입력 캐시 비활성화 설정을 확인하지 못했습니다. 새 프로세스, `--ephemeral`, 캐시 키 변경만으로 읽기·쓰기가 꺼졌다고 기록할 수 없습니다. `codex-luna/cache-preflight.json`에 차단 사유가 있습니다. 미호출 0토큰과 캐시 미사용 검증은 다릅니다.

이번에 추가한 정책은 API에도 적용합니다. 현재 Gemini Developer API 경로도 암묵적 캐시 차단 제어를 확인하지 못해 전송 전에 차단합니다. 사용량이 누락되면 0으로 간주하지 않습니다.

## {reference_run}의 실제 기록

|추론 설정|응답 수|입력 캐시 사용 응답 수|전체 입력 토큰|그중 캐시 입력 토큰|반환된 캐시 쓰기 토큰 합계|쓰기 항목 누락 응답 수|반환된 reasoning 출력 토큰|
|---|---:|---:|---:|---:|---:|---:|---:|
{usage_table}

표는 각 요청의 마지막 응답 사용량을 읽은 값이며 캐시 입력은 전체 입력에 포함됩니다. Codex CLI의 읽기 항목은 `cached_input_tokens`, 쓰기 항목은 `cache_write_input_tokens`입니다. 쓰기 합계는 반환된 항목만 합산하며, 누락 수가 0일 때만 모든 응답의 쓰기 사용량이 확인된 것으로 읽습니다. 쓰기 0이어도 읽기가 양수이면 캐시를 사용한 응답입니다.

{correction_note}

입력 캐시는 이미 계산한 입력 부분을 재사용하는 기능입니다. 이것만으로 이전 답변이나 reasoning 결과를 그대로 반환했다고 해석할 수 없습니다. 공식 문서는 출력이 새로 생성된다고 설명합니다. 위 사용량도 off와 on이 동일한 reasoning 설정으로 실행되었다는 근거가 아닙니다. [OpenAI 설명](https://developers.openai.com/api/docs/guides/prompt-caching).

## 비교 조건 보존

원문·변형 공개 입력, 비공개 정답, P0/P1·공통 프롬프트, V4 스키마의 해시가 이전 실행과 같습니다. {requests:,}요청 전체의 내용과 순서도 같습니다. 새 캐시 정책 기록과 그에 따른 요청 ID만 달라졌습니다. 기존 응답은 가져오지 않았습니다. 상세 해시는 `cache-audit.json`에 있습니다.

## 실행 가능한 경로를 정하기 위한 대안

OpenAI 공식 API는 GPT-5.6 이후 모델에서 `prompt_cache_options.mode="explicit"`를 지정하고 breakpoint를 넣지 않으면 입력 캐시 읽기·쓰기를 모두 하지 않는다고 설명합니다. 이 옵션을 구독 CLI에 적용할 방법은 확인되지 않았습니다. [캐시 제어 문서](https://developers.openai.com/api/docs/guides/prompt-caching).

동일 Luna를 유료 Responses API로 호출하는 대안을 `api-alternative-plan.json`에 정리했습니다. 현재 실험 어댑터는 미구현이며 실제 전송은 없습니다. {requests:,}회, 입력 약 {input_estimate}토큰(문자 수÷4 추정), 요청당 출력·reasoning 합계 1,000토큰 가정에서 **약 ${cost}**입니다. 입력 $0.20/M·출력 $1.20/M의 일반 API 단가로 계산했으며, Batch 할인·캐시 할인은 적용하지 않았습니다. 실제 토큰에 따라 달라지고 지출 상한은 아닙니다. [Luna 단가](https://developers.openai.com/api/docs/models/gpt-5.6-luna).

현재 설정은 계속 구독 CLI이며 유료 API로 자동 전환하지 않았습니다. API 전환은 과금 경로와 Codex가 붙이는 기본 지시문이 달라져 캐시 효과만을 분리한 비교라고 주장할 수 없습니다.

## 읽는 순서와 재생성

1. 이 문서 → `REPORT.md`: 차단 사유와 전체 계획·미실행 수.
2. `codex-luna/cache-preflight.json` → `state.json` → `events.jsonl`: 실제 사전 검사와 호출 0건.
3. `cache-audit.json`: 이전 사용량과 입력·요청 동일성 검사.
4. `api-alternative-plan.json`: 아직 실행하지 않은 유료 API 대안.

재생성은 `PYTHONPATH=src .venv/bin/python -m finarch.experiments.01-evaluation.04-validation.cache_audit --run reports/experiments-run/{run_id} --reference reports/experiments-run/{reference_run}`입니다. 이 명령은 저장된 파일만 읽으며 모델을 호출하지 않습니다. 별도 HTML을 만들지 않습니다.
