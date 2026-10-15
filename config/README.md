# 현재 설정 파일

| 파일 | 용도·읽는 코드 |
|---|---|
|llm.json|Preparation 기본 설정 및 공통 CLI/API 요청 설정|
|codex-profiles.toml|shared/providers/profiles.py가 읽는 모델·추론·전송 프로필|
|source-catalog.json|원천 데이터 준비용 목록, 입력 준비 및 검사|
|external-evidence.json|shared/calculation/external_evidence.py가 읽는 외부 근거 목록|
|hyperparameter.json|Preparation·Generation·Evaluation·Analysis의 schedule/run 설정|
|MODELS-README.md|모델 설정 안내|
|HYPERPARAMETER-README.md|배치 설정 안내|

읽는 순서: 이 문서 → 해당 안내 → 사용할 JSON/TOML. 보관 설정은 [archive](../archive/20260915-config-cleanup/README.md)에 있으며 실행 중인 run의 설정 사본은 변경하지 않았습니다. experiments pipeline은 기본으로 hyperparameter.json을 읽습니다. 명시적 --config와 기존 run의 동결 설정이 우선하므로 파일을 수정해도 이미 시작한 분석의 모델이 바뀌지는 않습니다.

## 스케줄링 숫자

시작 동시 문항 수, CPU 확인 주기·기준·증가량, 문항 내부 병렬 수는 hyperparameter.json이 기준입니다. [설명](../docs/01-dataset/90-operations/01-execution.md). 실행마다 적용 설정과 queue 진행 기록을 저장합니다.

계층: Preparation·Generation·Evaluation·Analysis 각각의 `schedule` / `run`. 모델 선택은 `run.models`, 프로필 정의는 `codex-profiles.toml`입니다. 생성 내 피드백 큐는 `generation.schedule.feedback`에서 관리합니다.

`evaluation.run.seed`는 **로컬 요청 목록을 섞는 순서용 값**이며 모델의 생성 seed가 아닙니다. 현재 Responses API 요청에는 전달하지 않습니다. 다른 값으로 요청 순서를 바꾸어 반복해도 모델 생성 seed를 제어한 실험으로 해석하지 않습니다. [공식 Responses 요청 항목](https://developers.openai.com/api/reference/resources/responses/methods/create)에는 생성 seed 항목이 없습니다(2026-09-27 확인).

## 실행 설정의 미사용 항목 제거

llm.json에는 실제로 읽는 실행 허용, 제공자, 역할 등록, 권한, 시간 제한, 프로필 선택 경로만 남깁니다. 하이퍼파라미터 선택이 적용되는 역할의 model/effort 중복값과 과거 실행 설명은 제거했습니다. 변경 전 설정과 검증 기록은 [보관본](../archive/20260915-config-unused-fields/README.md)에 있습니다. 모델 설정을 실행 시점에 완전히 고정하는 기능은 이 정리와 별개입니다.

## 과거 설정과 시험 기록

이전 Luna low API 시험 설정·당시 가격은 [20260916 기록](../reports/run/20260916-quality-v1/luna-low-api-setup.json)에 보관되어 있습니다. 현재 모델·추론·출력 한도는 과거 설명 대신 선택한 `codex-profiles.toml` 프로필을 확인합니다.

QI04는 전역 파일을 켜지 않고 **새 bundle의 별도 v2 hyperparameter 파일**에만 `generation.run.perturbation_policy: {"name":"bounded-coefficients-v1","seed":1}`를 넣어 사용합니다. bundle `config.json`의 `hyperparameter_path`를 해당 파일의 절대 경로로 지정합니다. 키가 없거나 `{"name":"legacy-v1"}`이면 기존 계수입니다. 최초 opt-in은 `02-generation/perturbation-policy.json`에 고정되며 seed/정책 변경 재개와 기존 legacy 실행의 전환은 거부합니다. [제한·재현](../reports/run/20260916-coefficients-v1/README.md)을 먼저 읽습니다.

## Evaluation / Analysis

네 단계 모두 같은 `schedule / run / models` 형식을 사용합니다. 모델명·추론 강도·API 출력 한도는 `codex-profiles.toml`, 대상·동시 실행·프로필 선택은 `hyperparameter.json`에서 관리합니다. 단가·가격 확인 날짜·키 경로·청구 설명은 hyperparameter에서 제거했습니다.

공통 파일의 Evaluation에는 과거 557원본 선택값이 남아 있습니다. 현재 TAT-QA 실행은 각 run의 동결 입력을 읽습니다. Analysis 기본은 `analysis.run.backend=codex`와 `sol61-low-cli`(gpt-6.1-sol/low), 동시 100건 고정입니다. API를 명시적으로 선택하면 `sol61-low-api` 프로필을 읽습니다. 모델별 실제 요청은 E02 manifest, 평가·분석 자료는 각 run에서 확인합니다.

풀이/API 분석 출력 한도는 새 요청부터 65,536입니다. Codex 분석에는 이 API 한도가 적용되지 않습니다. 이미 실행된 run의 설정·원응답은 보존합니다. [설정 항목과 길이 조정 근거](HYPERPARAMETER-README.md) · [실험 흐름](../docs/02-experiments/README.md).
