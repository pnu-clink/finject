# QI04 제한 계수 정책 — {run_id}

정책이 없으면 기존 legacy 동작입니다. 새 실행에서만 `generation.run.perturbation_policy`를 `{{"name":"bounded-coefficients-v1","seed":1}}`로 지정할 수 있습니다. 기존 config 파일은 바꾸지 않았습니다. 별도 v2 hyperparameter 파일을 새 bundle config의 `hyperparameter_path`로 지정합니다.

## 읽는 순서

1. `summary.json`: 실제 승인 test-0001 program 1개 × seed4 × VALUE/RELATION 2종 = Python 계획8건. 모델 호출0이며 새로운 생성 문장은 없습니다.
2. `coefficient-policy.json`: 계수·정책/input SHA256·고정 target·후보순서·시도/거절 이유·실제 branch program/graph/실행값입니다. 표시 답 정확성이나 전체624 품질 판정이 아닙니다.
3. `manifest.json`: 실제 원본/승인/graph 및 frozen dataset·전역 hyperparameter 파일 hash 불변 확인.
4. `checks.txt`, `checks.json`: 로컬 검사 결과. 초기 broad 검사 오류와 보정 내역은 `initial-checks.txt`에 남깁니다.
5. `events.jsonl`: 오프라인 생성 시작/완료 기록.

공통8892 viewer에서 `{run_id}`를 선택하면 저장 보고서와 원근거 hash 링크를 읽습니다. GET에서 선택/실행/모델 호출하지 않습니다. 브라우저 시각 확인은 메인 후속입니다.

## 실제 범위와 제한

VALUE 후보0.9/1.1, RELATION 후보0.5/2를 Decimal 문자열로 사용합니다. 정책·seed·원문/프로그램 input hash·case ID·family·factor의 SHA256 순서로 최대2개만 시도합니다. 대상과 피연산자 순서는 기존 그대로입니다. VALUE-before 선택을 after와 SOURCE1에, after를 SOURCE2에 상속하며 같은 binding인지 확인합니다. 이미 저장한 계획은 같은 정책/input일 때만 재사용합니다.

0 입력·지원 정의역 위반·exact 상쇄·기존 normalized 답 또는 고정 질문 정밀도에서 표시 답 불변을 거절합니다. 화폐는 부호 보존, count/shares/employees/people/units는 비음수 정수, percent는0~100의 제한 문법입니다. 모든 회계적·의미적 제약을 푸는 solver는 아닙니다. 미지원 단위 또는 명시적 질문 정밀도 부족은 미평가로 거절합니다. 질문의 nearest integer/whole number 또는0~4 decimal places만 지원하며 reference_precision도 일치해야 합니다. 정밀도를 바꿔 답을 다르게 만들지 않습니다.

전부 실패하면 NO_ADMISSIBLE_COEFFICIENT와 시도별 이유를 sidecar에 저장하고 LLM handler 없이 멈춥니다. +1·legacy 자동 복귀는 하지 않습니다. 새 generation snapshot과 정책 불일치/기존 legacy 실행의 뒤늦은 opt-in도 거절합니다. 선택값은 branch code·intent·allowed_numbers에 함께 반영되고 기존 graph/격리 Python 일치 검사도 유지합니다.

실제 전구간 생성/감사 API는 호출하지 않았습니다. 범위 밖 발견: 기존 `g03_verification.gg04_screen_recovery`는 config를 dict로 가정하지만 실행 드라이버는 Path를 전달하는 경로가 있습니다. QI04에서는 이 별도 EA gate 코드를 수정하지 않았으며 후속 실제 전구간 호출 전에 메인이 확인·보완해야 합니다. 이번에 검증한 경로는 v2 설정→runtime snapshot→run/g01→계획/로컬검사까지입니다.

대상 다양화·전수 LLM·frozen624 재생성은 미구현/미실행입니다. 후속 Luna-low4~6 API 검사는 메인의 별도 건수·비용 안내 후 진행하며 이번 완료에 포함하지 않습니다.

## 재현

`PYTHONPATH=src .venv/bin/python -m finarch.dataset.shared.review.coefficient_report --source reports/run/20260916-001 --output reports/run/새로운-실행명`
