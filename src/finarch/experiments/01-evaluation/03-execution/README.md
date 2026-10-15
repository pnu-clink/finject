# E03 Execution

[소스 전체](../../README.md) · [실험 문서](../../../../../docs/02-experiments/README.md) · [설정](../../../../../config/experiments/README.md)

run 대응: `01_evaluation/03_execution`.

E03.01 실행 조건 확인 → E03.02 LLM 풀이 → E03.03 시도 보존.

먼저 소량의 응답과 사용량을 확인한 후 후속 묶음을 제출합니다. 대기·실패·전송 여부 불명을 분리하고, 실패 시 원응답과 오류를 보존합니다. 제공자 처리 완료·로컬 수집 완료·형식 검사를 분리해 확인합니다.

## 사용법

다음 명령은 프로젝트 루트에서 실행합니다. `RUN_PATH`는 `prepare`가 출력한 실험 폴더입니다. 이미 생성한 실험을 이어갈 때는 같은 경로를 사용합니다.

```sh
RUN_PATH=reports/experiments-run/20261003-exp-004-tatqa-luna
PYTHONPATH=src .venv/bin/python -u -B -m finarch.experiments.pipeline run --evaluation-only --run "$RUN_PATH"
tail -f "$RUN_PATH/pipeline.log"
```

E03 전용 CLI를 새로 띄우는 대신 상위 pipeline을 사용합니다. `batches/<묶음>/job.json`의 Batch ID·제공자 상태·완료/실패 건수를 확인하고, 수집 후 `calls/`의 원응답과 시도 기록을 읽습니다. 동일 실행 중 프로세스나 기존 Batch를 중복 제출하지 않습니다.

`OPENAI_BATCH_SUBMITTED`는 제출, `OPENAI_BATCH_PROGRESS`는 제공자의 처리 현황, `OPENAI_BATCH_VALIDATION_PROGRESS`는 수집한 응답의 로컬 검사입니다. 제공자가 완료한 건수가 곧 로컬 형식 통과 건수는 아닙니다. `PIPELINE_EXIT`는 Evaluation의 한 조회 사이클 반환 기록이므로 전체 종료는 루트 `full_pipeline.status`로 확인합니다. 캐시 설정과 실제 usage 검사를 모두 확인하며 사용량 누락을 0으로 간주하지 않습니다.

## 파일 책임과 읽는 순서

|파일|입구|입력 → 처리 → 출력|
|---|---|---|
|[providers.py](providers.py)|`preflight / validate_request / call`|요청·설정 → 스키마 정의·입력·조건 검사, Haiku 5.5의 effort·thinking_type·출력 상한과 OFF/xhigh·max 불가 검사 → 제공자 선택·원응답·형식 상태|
|[orca_api.py](orca_api.py)|`validate_model / body_for / call / parse_response / accepted_returned_models / configure_returned_model / revalidate_returned_models`|동결 DeepSeek V4.1 Flash 요청 → R⁻ disabled / R⁺ enabled·max, run별 캐시·반환 모델명 승인 검사·HTTP 1회 전송 → raw·추론 trace·캐시 사용량·반환 비용. 승인된 날짜형 응답 이름만 해당 run에서 추가 허용하며 요청 모델과 원응답은 유지. 저장된 모델명 검사 오류는 원래 result를 보존하고 E04 재검사하며 재호출하지 않음. 연결 끊김은 UNKNOWN_DELIVERY·usage 미확인으로 보존하며 자동 재전송하지 않음|
|[anthropic_api.py](anthropic_api.py)|`body_for / call`|동결 요청 → 4.5 budget 또는 5.5 effort·adaptive/disabled·전송용 JSON schema → 실제 Messages body·원응답|
|[openai_batch.py](openai_batch.py)|`process`|고정 요청 → OpenAI Batch 제출·조회·수집 → Batch ID·원응답|
|[anthropic_batch.py](anthropic_batch.py)|`split_requests / process_chunk / process`|고정 요청 → 설정된 조건의 선행 묶음·2/4조건 모두 유효한지 검사 → 후속 Batch 제출·같은 ID 조회·수집·원응답 보존. 선행 실패는 후속 제출 중단|
|[gemini_batch.py](gemini_batch.py)|`process / collect / collect_submitted`|고정 요청·캐시 검사 → Native Gemini Batch 제출·30초 조회·수집 → Batch name·진행 로그·원응답·사용량. `submit_all_before_poll=true`는 분할 배치를 순차 제출한 뒤 저장된 ID로 수집. `collect_submitted`는 이미 접수된 ID만 수집하며 새 제출·거절 재시도를 하지 않음|
|[call_layout.py](call_layout.py)|`publish`|시도 결과 → 문항·조건별 경로 → 원응답 연결|
|[output_budget.py](output_budget.py)|`configure / policy_for / prepare_attempt / retry_truncated`|run별 승인·동결 요청·이전 시도 → 기본 상한 / 실제 length 종료만 2배 확대 → 시도별 cap·출처 해시. 일반 형식 실패·전송 불명은 재호출하지 않으며 최대 상한에서 종료|

```mermaid
flowchart LR
 IN["입력·설정"]
 subgraph F0["01-evaluation/03-execution/providers.py"]
  S0["E03.01 동일 스키마 정의 검사 · 변경된 정의는 새 검사"] --> N0["입력·조건 매 요청 검사 / preflight / call · Haiku 5.5 OFF/xhigh·max 차단 · Gemini level 검사"]
 end
 subgraph F1["01-evaluation/03-execution/openai_batch.py"]
  N1["process"]
 end
 subgraph F2["01-evaluation/03-execution/anthropic_batch.py"]
  N2["E03.A02 split_requests · 설정된 조건의 선행 묶음"] --> A1["E03.A03 prepare_job · body/schema·동결 해시"]
  A1 --> A2["E03.A04 submit · Batch ID 보존"] --> A3{"E03.A05 poll · 같은 ID 완료?"}
  A3 -->|대기| A3
  A3 -->|완료| A4["E03.A06 raw·사용량·E04 검사 보존"] --> A5{"선행 조건 모두 VALID?"}
  A5 -->|통과 · 후속 묶음| A1
  A5 -->|실패 · 후속 미제출| ERR
  A4 --> OUT
 end
 subgraph F5["01-evaluation/03-execution/anthropic_api.py"]
  H0["E03.A01 body_for · 5.5 adaptive/disabled + output_config.effort · 전송 schema"]
 end
 subgraph F6["01-evaluation/03-execution/orca_api.py"]
  O1["E03.O01~02 동결 모델·OFF/max·schema·run 캐시 승인 검사"] --> O2["E03.O03 실제 HTTP 1회 · redirect 금지"]
  O2 --> OM{"E03.O07 반환 모델명 · 기본 식별자 또는 해당 run의 날짜형 승인?"}
  OM -->|허용| O3["E03.O04 raw·사용량·reason trace 보존 · E04 형식 검사"] --> OP{"OFF/ON 선행 응답 VALID?"}
  OM -->|미허용 · 원응답 보존| ERR
  OS["E03.O07.1 configure_returned_model · runtime 승인 기록"] --> OM
  OR["E03.O07.2 revalidate_returned_models · HTTP 200·전송 요청 대조 · 원래 result와 raw 보존 · 새 호출 0건"] --> OM
  OP -->|통과 · 후속 묶음| O1
  OP -->|실패 · 미평가| ERR
  O2 -->|429 · 저장된 최대 회차·Retry-After| O1
  O2 -->|연결 끊김| OD["E03.O06 UNKNOWN_DELIVERY · HTTP 시각·요청 해시·오류 보존"]
  O2 -->|그 밖의 전송 불명·인증·한도| ERR
  O3 --> O4["E03.O05 UTC 단가 추정·제공자 반환 비용 분리"] --> OUT
 end
 subgraph F7["01-evaluation/pipeline.py"]
  OD --> DC{"E03.D01 run별 계속 실행 승인 · OFF/ON 확인 · 같은 묶음 응답 수신?"}
  DC -->|예 · 끊긴 요청 재전송 없음| DN["E03.D02 미전송 요청만 다음 묶음"] --> O1
  DC -->|아니요 · 응답 없는 묶음 포함| ERR
 end
 subgraph F8["01-evaluation/03-execution/output_budget.py"]
  L1["E03.L01 configure · 승인·run·동결 manifest 해시 검사"] --> L2["E03.L02 prepare_attempt · 기본 상한 / 저장된 확대 상한 · 요청 사본"] --> O1
  O3 --> L3{"E03.L03 실제 length 종료 · 최대 상한 미도달?"}
  L3 -->|예 · 이전 상한의 2배 · 새 attempt| L2
  L3 -->|아니요 · 상태 보존| OUT
 end
 subgraph F3["01-evaluation/03-execution/call_layout.py"]
  N3["publish"]
 end
 subgraph F4["01-evaluation/03-execution/gemini_batch.py"]
  G1["E03.G01 동결 요청·캐시 승인 검사"] --> G2["E03.G02 Batch 제출·name 보존"]
  G2 --> GA{"전체 제출 후 조회 설정?"}
  GA -->|예 · 남은 PREPARED 배치| G2
  GA -->|제출 완료 또는 기본 순차 처리| G3{"E03.G03 같은 name으로 조회·진행 로그"}
  G3 -->|대기·30초| G3
  G3 -->|완료| G4["E03.G04 raw 보존·형식·캐시 사용량 검사"] --> OUT
  G2 -->|전송 불명| ERR
  G2 -->|제공자 거절 · 추가 제출 중단| ERR
  CS["collect-gemini-batches · 기존 name만 선택 · 거절 상태 보존"] --> G3
 end
 IN --> S0
 S0 -->|잘못된 스키마| ERR
 N0 --> OUT["저장 자료·상태"]
 N0 -->|실패| ERR["오류·미평가 기록"]
 N0 -->|Gemini Batch| G1
 N0 -->|Anthropic Batch| H0 --> N2
 N0 -->|Orca API| O1
 classDef python fill:#e3f2fd,stroke:#1565c0;
 classDef file fill:#eceff1,stroke:#607d8b;
 class S0,N0,N1,N2,N3,G1,G3,G4,CS,H0,A1,A3,A4,A5,O1,O3,O4,OP,OM,OS,OR python;
 class L1,L2,L3 python;
 classDef llm fill:#ede7f6,stroke:#673ab7;
 class G2,A2,O2 llm;
 class IN,OUT,ERR file;
```

회색은 입력·출력 파일, 파랑은 파일의 Python 함수입니다. 표의 함수는 해당 책임을 담당합니다. 세부 실행 순서·LLM 분기는 [실험 문서](../../../../../docs/02-experiments/README.md)의 같은 번호 단계를 읽습니다.

이 README는 `src/finarch/documentation/templates/source-layout/experiments/01-evaluation/03-execution.md`에서 생성합니다.

승인된 Orca run에서 `configure-output-budget --model-key <key> --authorization '<실제 지시>' --base-output-tokens 8194`로 정책을 기록한 뒤, `run --evaluation-only --resume-limits`로 중단된 Evaluation을 재개합니다. `runtime-overrides.json`은 동결 config와 분리하며 실제 cap·원본 요청 해시는 새 attempt의 request·started·result에 저장합니다. `publish`는 최신 시도의 실제 요청을 표시합니다. `OUTPUT_BUDGET_INCREASED`는 다음 length 재시도 상한이며, 실제 전송은 `OUTPUT_BUDGET_ATTEMPT`와 provider-request-wire.json에서 확인합니다.
