# GPU-2 FinanceReasoning 1,080문항 전달 자료

실행: **$run_id** · 모델: **$model** · 원본 선정 run: **$source_run**.

읽는 순서: [상태](state.json) → [전달 로그](events.jsonl) → [원천·프롬프트 해시](source-provenance.json) → [실행 설정](config.json) → [계획](01_evaluation/02_request/plan.json) → [실제 요청](01_evaluation/02_request/)입니다.

| 파일 | 역할 |
|---|---|
| `00_input/public.jsonl` | 공개 질문·문맥·소수 자리수. 원본 1,080개와 변형 7,560개 |
| `00_input/private.jsonl` | 로컬에만 둔 정답·제작 분류. A100 전달 파일에는 없음 |
| `01_evaluation/02_request/common.md` | 현재 공통 풀이 프롬프트 |
| `01_evaluation/02_request/prompt-unguided.md` | 모델에 `classification=null`을 직접 지시 |
| `01_evaluation/02_request/prompt-guided.md` | 다섯 분류 중 하나를 직접 선택하도록 지시 |
| `01_evaluation/02_request/response.schema.json` | FinancialAnswerV7 응답 스키마 |
| `01_evaluation/02_request/$model_key/manifest.jsonl` | 모델당 34,560개 동결 요청. 질문·프롬프트·스키마·조건을 함께 저장 |
| `a100-runtime.json` | 기존 측정 후보 설정. 원격의 토큰 길이·GPU 점검 전에는 실행값으로 확정하지 않음 |
| `transfer-manifest.json` | A100에 보낼 파일의 SHA-256. private 파일은 포함하지 않음 |

원본·변형 8,640개 × Unguided/Criteria-Guided × Reasoning OFF/ON = **모델당 34,560건**입니다. 이번 준비는 파일 생성과 해시 검증만 수행하며 모델 요청은 0건입니다. 기존 557문항 평가 원응답은 재사용하지 않습니다.

GPU-2 담당 세션이 토크나이저 입력 길이, 현재 GPU 점유, 모델 revision, 형식 제약과 cache 지표를 확인한 뒤 실행합니다. 과거 A100 `remote.py`와 `collect.py`에는 17,824건 고정 값이 있으므로 새 요청 수에 맞춰 점검해야 합니다. 전송 여부가 불명확한 요청은 원기록을 남기고 임의로 재전송하지 않습니다.

실행 상태와 결과는 실험 뷰어 `http://127.0.0.1:8894/`에서 이 실행을 선택해 확인합니다. 현재 `TRANSFER_READY`는 결과가 아니라 파일 준비 상태입니다.
