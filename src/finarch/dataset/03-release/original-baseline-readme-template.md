# QI02 原문 baseline 입력 준비 — {run_id}

원문 {originals}개 → frozen 변형 {variants}개 연결, 준비 {prepared}개·미완료 {not_prepared}개입니다. 출처는 FinanceReasoning {FinanceReasoning}, TAT-QA {TAT_QA}입니다. **실제 Qwen baseline 호출0·의미 검토0**이며 준비 완료를 실험 완료로 해석하지 않습니다.

## 읽는 순서

1. `summary.json`: 단위는 원문92와 변형624로 구분합니다.
2. `public/dataset.json`: 모델 입력용 id/context/question만 있습니다. 원문은 변형을 만든 승인 Preparation C/Q이며 raw 제공자 원문과 구별합니다.
3. `public/requests/<case>.json`: 실제 저장된 624개 요청에서 동일함을 확인한 model/system/schema/temperature0/max_tokens4096에 원문 Q/C만 넣었습니다. 네트워크 전송은 없습니다.
4. **비공개** `private/originals.json`: reference/gold·출처·승인 차수·원본/작업본 hash·case별 파생 variant 연결·NOT_REVIEWED·미완료 이유입니다. public 입력과 함께 모델에 보내지 않습니다.
5. `manifest.json`: 입력 hash 불변 확인과 public 출력 hash입니다. `sidecar-schema.json`은 private 보고서, `public-input-schema.json`은 public 입력의 실제 JSON Schema입니다.
6. `events.jsonl`, `checks.txt`: 생성 단계와 로컬 검사 결과입니다.

공통 viewer에서 `{run_id}`를 선택합니다. 화면은 연구자용 private 보고서를 읽으므로 public 배포용 화면이 아닙니다. GET에서 분석·쓰기·모델 호출을 하지 않습니다. public/private는 파일 및 요청 경계이며 OS 접근권한 격리를 뜻하지 않습니다.

## 보류·제한

5개 원문 의미 검토도 이번 최소 범위에서는 NOT_REVIEWED로 남겼습니다. 0017 operating income/charges의 의미 정합성 문제를 전체 불량 확정이나 새 판정으로 확대하지 않습니다. gold는 검증 근거와 별개입니다.

Qwen baseline은 진행 중 실험과 비교 조건 보존을 위해 보류했습니다. 저장 model alias만으로 배포 revision을 확정하지 않았습니다. 후속 실행 시 같은 revision·프롬프트·schema·temperature·출력 상한을 확인해야 합니다. 나중의 Luna-low 4~6회 품질 API 검사는 Qwen baseline의 대체가 아닙니다. qwen_repeated.py와 기존 실험은 변경하지 않았습니다.

## 재현

`PYTHONPATH=src .venv/bin/python -m finarch.dataset.03-release.original_baseline --source reports/run/20260916-001 --quality-root reports/run/20260916-quality-v1 --output reports/run/새로운-실행명`

기존 output은 거부합니다. 중복 variant·잘못된 parent·원자료 hash/차수/QC 불일치는 통과시키지 않으며 일부 불명확한 원문은 NOT_PREPARED와 이유를 보존합니다. public 필드 allowlist와 private 값 변경에 대한 요청 불변 검사를 사용하며, 본문에 우연히 있는 정답과 같은 숫자를 누출로 오판해 제거하지 않습니다.
