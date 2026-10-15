# EA 역산 독립 재검토

`dataset.jsonl`의 삭제 후 Q/C만 사용하여 {cases}문항 × EA 두 유형, **{items}건**을 Codex 에이전트가 개별 검토했습니다. 기존 `ea_inverse_review.py`의 누락 수량·역산 여부·이유·근거·식 계약을 따르며, 외부 모델/API 호출은 0건입니다. production 판정과 원본 데이터는 변경하지 않았습니다.

읽는 순서는 다음과 같습니다.

1. [summary.json](summary.json): 해시·검사 결과·출처/유형별 전이 건수입니다. 새 판정은 true {new_true}건, false {new_false}건입니다. 기존 완료 판정 중 {changed}건이 바뀌었으며, 기존 미기록·호출 실패 {newly_reviewed}건은 새로 판정했습니다.
2. [changed-decisions.jsonl](changed-decisions.jsonl): 기존 완료 판정이 뒤집힌 항목의 이전·새 이유와 식입니다. [comparison.jsonl](comparison.jsonl)은 전체 {items}건을 비교합니다. UNKNOWN은 false가 아닙니다.
3. 새 결과 `{result}`: 기존 합본과 같은 ID·순서·Q/C, 같은 최종 JSON schema를 사용합니다. 기존 파일의 바이트 백업은 `{backup}`입니다.
4. [qc-only.jsonl](qc-only.jsonl)은 검토 입력, [agent-decisions.jsonl](agent-decisions.jsonl)은 개별 검토 기록, [run.json](run.json)은 작업의 시작·완료 정보입니다. 수식 후보는 [proposals.jsonl](proposals.jsonl)에 있으며 후보 자체는 판정 근거가 아닙니다.

합계·부분합, 부호 있는 차이·잔액 이동, 비율·회계 정의, 완전한 비중·확률 합, 성장률, 재기재 값과 기간·회사·단위 및 반올림을 검토했습니다. 다른 EA 유형, 원문, gold, 삭제 계획과 이전 판정의 숫자는 복원 근거로 사용하지 않았습니다. true는 남은 자료에서 적용 가능한 식을 확보했다는 판정입니다. false는 해당 기준에서 유일한 복원을 확립하지 못했다는 판정이며 모든 가능한 논리 경로의 수학적 불가능 증명이 아닙니다. 독립적인 사람의 의미 검증은 **PENDING**입니다.

Python 검사는 형식·입력 일치·인용 좌표·기록된 식의 산술을 확인합니다. 산술 검사 통과가 식의 의미 타당성이나 정답 gold를 확정하지 않습니다. 기존 파일과 dataset 해시는 보존했습니다. 공통 dataset viewer의 `/ea-inverse` 화면에서 실제 새 결과와 기존 결과를 열람합니다. 뷰어 검증 상태는 `summary.json`에 별도로 기록합니다.

이 README는 `src/finarch/documentation/templates/ea-inverse-offline-review.md`에서 생성합니다. 재현할 때에는 저장된 Q/C-only 검토 기록을 준비하고 `PYTHONPATH=src .venv/bin/python src/finarch/dataset/checks/ea_inverse_offline_review.py --finalize`를 사용합니다. 이 명령은 새 의미 판정을 자동 생성하지 않으며, 이미 존재하는 새 결과를 덮어쓰지 않습니다.
