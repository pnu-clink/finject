# 02 Analysis — 결과 관계 분석

출처: {source}의 Evaluation. 상태: {status}.

1. [A01 결과 취합](01_results/README.md): 전체 응답과 이미 저장된 숫자 비교를 연결합니다.
2. [A02 관계 비교](02_comparison/README.md): 원본/변형·조건·유형·답/분류/설명/근거의 관계를 비교합니다.
3. [A03 연구 해석](03_research/README.md): 대표 사례·반례·대안 설명·한계를 정리합니다.
4. [A04 사분면 정리](04_quadrant/README.md): 연구 발견 F만 의미별로 묶어 네 풀이 조건에 연결합니다. 뷰어 **03 사분면 비교 → D01 연구발견**에서 읽습니다.
5. [A02 실패·검토 불가 자료](04_failure_analysis/README.md): 대상 모델의 explanation·evidence와 원문, 형식 오류, Analysis 검토 사유를 함께 확인합니다. A02 취합 때 Python으로 생성하며 기존 경로는 보존합니다.
6. 시간 기록: 실행 시 생성되는 `timing.md`·`timing.json`·`timing-events.jsonl`에서 단계별 경과 시간과 개별 호출 시간을 확인합니다. 실험 뷰어의 A01 화면에도 표시합니다.

미검토(NOT_REVIEWED)·검토 실패(REVIEW_FAILED)는 재검토 대상이고 해결 전에는 A03 진행을 막습니다. 검토 불가(NOT_REVIEWABLE)·입력 원문 없음(SOURCE_MISSING)은 원응답과 사유를 보존하고 A03에 한계로 전달합니다. 원응답·gold·점수는 수정하지 않습니다. 숫자 일치, 모델 분류, 설명에 드러난 풀이 경로는 서로 다른 관찰입니다.

## 사용법

분석을 실행하기로 정한 뒤 프로젝트 루트에서 `PYTHONPATH=src .venv/bin/python -u -B -m finarch.experiments.pipeline analysis --run reports/experiments-run/{run}`을 사용합니다. Evaluation을 재호출하지 않고 A01 → A02 → A03 → A04를 재개합니다. `configure-analysis`는 모델·effort·backend 동결, `configure-schedule`은 동시 호출 등 운영 설정 변경이며 모델 호출은 하지 않습니다. 중지 기록은 별도로 해제되어야 합니다.

진행은 각 단계 state·manifest·calls에서, 시간은 timing.json에서 확인합니다. API backend의 대기는 같은 Batch ID로 이어 읽고 응답 미확인 시도를 자동 중복 호출하지 않습니다.

승인된 Codex A02 실패 복구는 `configure-analysis-retries --run reports/experiments-run/{run} --authorization '<실제 지시>'`로 정책을 기록한 뒤 같은 pipeline의 `analysis-sequence --run reports/experiments-run/{run}`으로 진행합니다. `retry-policy.json`이 존재할 때 기존 호출을 모두 수집한 후 서버 혼잡·종료가 확인된 TIMEOUT만 60/120/240초 대기, 최대 3회 재시도합니다. `02_comparison/retry-rounds/round-*.json`에 대상 ID·대기·시도 횟수·결과를 보존하며 성공 응답은 재호출하지 않습니다. A02 취합 후 미검토·검토 실패가 없으면 검토 불가 사유를 보존하고 A03를 시작하고, 횟수 소진·미확인 요청은 이유를 남기고 중단합니다. 시간 표의 **A02 실패 확인·대기·재시도**에는 대기와 재호출 시간이 함께 포함됩니다.

`--retry-validation-failures --retry-research`를 명시한 확장 정책은 검사 실패·출력 잘림·일시 오류도 포함하고 A03에 같은 단계별 재시도를 적용합니다. 실제 범위는 `retry-policy.json`, 변경 이력은 `retry-policy-extension-*.json`에서 확인합니다. 확장으로 사용한 회차를 초기화하지 않습니다. A03의 재시도는 `03_research/retry-rounds/`와 **A03 실패 확인·대기·재시도** 시간 항목에서 확인합니다.

Codex는 첫 1건의 응답을 기다리지 않고 설정한 동시 한도로 시작하며 개별 응답 검사는 유지합니다. `resume-analysis --run <run> --authorization '<실제 지시>'`는 중지된 Analysis 대기만 해제합니다. 중지된 시도는 응답 미확인으로 보존하고, 아직 보내지 않은 요청만 재개하며 Evaluation 대기는 해제하지 않습니다.

모델 변경으로 재시작한 run은 `restart.json`의 archive 경로에서 이전 분석 원응답·실패·중지 기록을 확인합니다. 새 모델은 `config.json`, 실제 호출은 각 단계 provider-request.json을 읽습니다. 중앙 기본값은 `config/hyperparameter.json`에서 선택하고 모델·effort는 `config/codex-profiles.toml`에서 정의합니다.

완료된 A03의 연구 발견만 후속 정리할 때는 `analysis-postprocess --run reports/experiments-run/{run}`을 사용합니다. A02/A03 성공 호출은 재실행하지 않고 A04의 동결 prompt/schema/manifest와 calls를 사용합니다.
