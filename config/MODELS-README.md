# 파이프라인 모델 선택 · 2026-10-01

새 호출에 사용하는 `gpt-5.6-luna`를 **`gpt-6-luna`**, `gpt-5.6-sol`을 **`gpt-6.1-sol`**로 교체했습니다. 프로필 ID·effort·출력 한도·총 토큰 한도·프롬프트·응답 스키마는 유지합니다.

|영역·용도|선택 프로필|모델 / effort|출력 / 총 토큰 한도|
|---|---|---|---|
|Preparation · 원문 검토·수정|luna-max-api|gpt-6-luna / max|32,768 / 500,000|
|Preparation · POT·독립 재풀이|sol-medium-api|gpt-6.1-sol / medium|128,000 / 500,000|
|Preparation · 의미 검증·예외 피드백|luna-max-api|gpt-6-luna / max|32,768 / 500,000|
|Generation · 문장 생성·완성문 검증·피드백|luna-max-api|gpt-6-luna / max|32,768 / 500,000|
|Generation · EA 역산가능성 검토|sol61-high-api|gpt-6.1-sol / high|32,768 / 500,000|
|공통 · 실패 해석·화면 번역|luna-max-api|gpt-6-luna / max|32,768 / 500,000|
|명시적 소규모 테스트|luna-low-api|gpt-6-luna / low|32,768 / 500,000|
|Evaluation · reasoning OFF / ON|luna6-none-api / luna6-medium-api|gpt-6-luna / none·medium|65,536 / 실험 설정 기준|
|Analysis · A02·A03 기본|sol61-low-cli / sol61-low-api|gpt-6.1-sol / low|65,536 / 실험 설정 기준|

2026-10-08부터 EA 역산은 일반 검증과 분리한 `ea_inverse_review` 목적을 사용합니다. `generation.run.models.ea_inverse_review`와 공통 `[selection].ea_inverse_review`는 `sol61-high-api`를 선택합니다. 역산 true/false나 호출 실패는 제작 PASS/FAIL을 바꾸지 않습니다. 이미 저장된 run 설정·결과는 변경하지 않습니다.

제작 모델 정의는 [codex-profiles.toml](codex-profiles.toml)에 있습니다. Schedule은 [hyperparameter.json](hyperparameter.json)의 Preparation/Generation `run.models`에서 **목적별 프로필**을 선택합니다. Schedule 밖의 공통 호출은 `codex-profiles.toml`의 `[selection]`을 읽으며, 명시적인 호출별 `profile_id`가 우선합니다. `generation`/`validation` 두 선택만 바꾸면 목적별 설정까지 모두 바뀐다고 간주하지 않습니다. 실험 기본 모델 선택도 hyperparameter.json의 Evaluation/Analysis `run.models`를 읽습니다. Analysis 기본은 `sol61-low-cli`(gpt-6.1-sol/low)이며 동시 100건 고정입니다. 과거 experiments/*.toml은 명시적 --config 호환용으로 유지합니다. 실제 실행은 run의 동결 config와 provider-request.json을 확인합니다.

명시적 CLI 프로필 `luna-none`·`luna-low`·`luna-medium`·`luna-max-cli`도 `gpt-6-luna`로 교체했습니다. Astra와 다른 모델 선택지는 이번 두 모델 교체 대상이 아니며, 기존 `gpt-6-sol` 실험 프로필은 과거 설정 호환용으로 유지합니다. 이미 동결된 run 설정·원응답·가격 기록은 소급 변경하지 않습니다. 실제 요청에는 해석된 모델·effort·프로필 해시를 기록합니다.

가격 추정표에는 새 두 모델의 [공식 Luna 문서](https://developers.openai.com/api/docs/models/gpt-6-luna)·[공식 Sol 문서](https://developers.openai.com/api/docs/models/gpt-6.1-sol) 기준 단가를 추가했습니다. 이전 모델 단가는 과거 사용량 해석을 위해 보존합니다. 긴 입력의 별도 단가가 정의되지 않은 범위는 추정액 미확인으로 유지하며 0달러로 처리하지 않습니다.

이 변경의 검사는 설정 해석·요청 생성·로컬 응답 대역·Export 회귀 검사입니다. 유료 모델 호출은 없으며 실제 모델의 의미 품질 개선은 아직 측정하지 않았습니다.
