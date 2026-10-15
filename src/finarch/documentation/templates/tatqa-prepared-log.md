# TAT-QA 결과 전달·Luna Evaluation 시작 기록

## 이번 작업

사용자 지시로 `20261003-003`의 결과를 `data/prepared/tatqa/20261003-003`에 정리하고, 사용자가 선택한 Luna Native OpenAI Batch Evaluation을 시작합니다. 실제 제출·진행 상태는 아래 validation과 실험 run의 state/job 파일에서 확인합니다.

## 읽는 순서·파일 역할

1. [데이터 전달본 README](../../data/prepared/tatqa/20261003-003/README.md): 437원본 결과 보존, 291문항군의 자동 PASS 범위, 원천 경로·해시와 파일 역할.
2. `validation.json`: 원천/전달 해시, 선정 ID·공개 입력 동일성, 4개 로컬 회귀 검사, 문서 검사, 실제 Batch·뷰어 조회 결과와 검증 한계.
3. `events.jsonl`: 데이터 전달·검사·실험 시작 연결 기록.
4. `prepare.log`: 기존 `finarch.experiments.pipeline prepare`의 실제 출력.
5. [실험 README](../../reports/experiments-run/20261003-exp-001-tatqa-luna/README.md), 실험의 `authorization.json`, `launch-verification.json`, `state.json`, `pipeline-process.json`, `pipeline.log`: 동결 입력·승인 범위·배경 pipeline과 현재 상태.
6. 실험의 `01_evaluation/02_request/plan.json`·`luna-api/manifest.jsonl`, `01_evaluation/03_execution/luna-api/batches/*/job.json`: 예상 요청·비용, 실제 조건별 요청과 제출 Batch ID.

README는 `src/finarch/documentation/templates/tatqa-prepared-log.md`에서 생성합니다.

## 데이터·호출 범위

- 원본·7변형 모두 자동 PASS인 **291문항군**. 자동 PASS는 사람 승인 또는 의미 정답 확정과 다릅니다.
- 원본 291＋변형 2,037＝**2,328개 공개 입력**.
- Unguided/Guided × Reasoning OFF(none)/ON(medium)＝**9,312개 평가 요청**. 같은 설정의 네 번 반복이 아닙니다.
- 원본 외부사용 분류는 55건이 확인 조건 충족, 236건은 조건 미충족이며 private에만 전달합니다. 이 분류가 대상 모델의 실제 지식 사용을 뜻하지 않습니다.
- Luna 모델은 `gpt-6-luna`, Native OpenAI Batch, cache off입니다. 실제 cache read/write 사용량은 수집 후 확인하며 아직 0이라고 단정하지 않습니다.
- 비용은 요청당 출력 1,000토큰·문자 수 기반 입력 추정에서 **약 $3.07**입니다. 추론을 포함한 실제 출력 토큰에 따라 달라지며 청구서 금액이 아닙니다. [공식 모델·가격 안내](https://developers.openai.com/api/docs/models/gpt-6-luna).
- Analysis와 새로운 의미 judge 호출은 이번 실행에 포함하지 않습니다. `run --evaluation-only`와 Analysis paused를 사용합니다.

## 변경 파일과 책임

|파일|역할|
|---|---|
|`src/finarch/dataset/03-release/export_run_results.py`|`--prepared-output`으로 기존 결과를 새 data 폴더에 해시 확인 후 전달. 재생성·덮어쓰기 없음|
|`src/finarch/experiments/00-input/dataset.py`|`results_path` 전달본을 실제로 읽고 원천·사본·현재 제작 상태를 재확인|
|`src/finarch/experiments/00-input/edit_provenance.py`|후속 메타정보 연결도 같은 전달 경로 사용|
|`config/experiments/config.toml`|새 source_run/results_path/input_path, count=291, private 외부사용 분류 필수, Luna 실험 이름|
|`src/finarch/experiments/checks/test_prepared_results.py`|바이트·읽기 동일성, 실패 보존, 전달본 변경·원천 변경·다른 원천 거부 검사|
|단계별 documentation 템플릿|전달 순서·책임·실제 코드 흐름과 새 자료 연결|

## 확인 화면

[Luna 실험 진행 화면](http://127.0.0.1:8894/?run=20261003-exp-001-tatqa-luna&tab=progress) · [Luna 실험 입력·개요](http://127.0.0.1:8894/?run=20261003-exp-001-tatqa-luna&tab=overview) · [원천 제작 화면](http://127.0.0.1:8893/?run=20261003-003).

실험 결과 폴더에 별도 HTML을 만들지 않습니다. API에서 최신 자료를 읽었는지와 실제 브라우저 화면 확인 여부는 validation.json에서 구별합니다. 제출 완료는 모델 응답 수집·형식 검사·RQ1 의미 판정 완료와 다릅니다.
