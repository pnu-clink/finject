# 실험 저장·운영

[문서의 단계·요구·실행 흐름](../../../../docs/02-experiments/README.md) · [전체 소스 구조](../../../../docs/01-dataset/90-operations/05-source-layout.md)

이 폴더는 위 문서 단계의 실행 코드를 소유합니다. 결과의 물리 경로는 기존 run 계약을 따릅니다.

|파일|역할|
|---|---|
|[label_migration.py](label_migration.py)|Reconcile the delegated EA metadata rename against its original backup.|
|[storage.py](storage.py)|원자적 저장·동결 해시·잠금. `configuration`은 run ID를 확인해 cache-exceptions.json의 모델별 승인을 별도로 읽습니다. 실제 Python 명령과 단계·Batch name·진행 이벤트를 events.jsonl 및 pipeline.log에 기록합니다.|
|[settings.py](settings.py)|기본 hyperparameter.json의 schedule/run과 공통 codex-profiles.toml을 해석해 실행 설정을 고정합니다. Gemini 3.8 Flash와 3.5 Flash-Lite는 추론 OFF를 차단합니다. 3.8은 low/medium/high, 3.5 Lite는 minimal/low/medium/high 중 명시한 ON 수준만 준비합니다.|
|[analysis_variant.py](analysis_variant.py)|완료된 Evaluation의 동일 파일·태그·새 설정 → 기존 분석을 재사용하지 않는 별도 Analysis run 준비. 모델 호출 없음.|
|[execution_start.py](execution_start.py)|동결 설정·실제 단계 → 모델·effort·작업·요청 수·동시 수를 stdout·pipeline.log에 실행 전 출력.|
|[analysis_restart.py](analysis_restart.py)|중지·프로세스 종료·Evaluation 완료 확인 → 이전 분석 전체 보존 → 동일 입력의 새 모델 요청 동결. 모델 호출 없음.|
|[analysis_sequence.py](analysis_sequence.py)|pipeline.py analysis-sequence의 승인된 순서대로 Analysis만 실행·상태 갱신. --after-analysis-run은 선행 analysis·full_pipeline의 COMPLETE를 모두 확인한 뒤 시작. 실패·미확인 선행 건은 자동 재호출하지 않으며 Evaluation 재호출 없음.|
|[execution_control.py](execution_control.py)|선택 run의 A02/A03/A04 실행 중지·부분 출력 보존. resume-analysis는 종료 확인된 중지 요청을 응답 미확인으로 보존하고 Analysis 대기만 해제. 재전송·Evaluation 해제 없음. retry-analysis-requests는 종료 확인·명시 승인된 ID만 한 번 재호출하며 다른 요청은 보존.|
|[run_layout.py](run_layout.py)|새 Input/Evaluation/Analysis 경로와 과거 실행 경로를 구분합니다.|
|[run_documentation.py](run_documentation.py)|단계별 입출력·실행 파일·사용법·읽는 순서를 README 템플릿으로 생성합니다. 루트 사용법과 run별 output_budget의 기본 상한·확대 조건·기록 위치는 현행 안내에서 갱신하며 run에 동결된 정의 템플릿은 보존합니다.|

## README 생성과 갱신

정적 소스·단계 안내는 프로젝트 루트에서 `PYTHONPATH=src .venv/bin/python -B src/finarch/documentation/manage.py refresh` 후 `validate`로 확인합니다. run 안내는 실제 Preparation·수집·보고의 `run_documentation.render()`가 저장 상태와 템플릿으로 생성합니다. 문서 갱신 자체는 모델 호출을 만들지 않습니다.

```mermaid
flowchart LR
 subgraph CONFIG["90-operations/settings.py"]
  C1["C01 load: 기본 hyperparameter / 명시 config 읽기"] --> C2{"C02 Gemini level / Orca 동결 모델·OFF/max·출력 상한 확인"}
  C2 -->|ON · 해당 모델 지원 수준| C3["C03 준비 설정 반환"]
  C2 -->|OFF·미지원 수준| FAIL["run 생성 전 오류"]
 end
 subgraph STORE["90-operations/storage.py"]
  S1["S01 configuration: 동결 config 읽기"] --> S2["S02 run ID 일치하는 별도 캐시 승인 연결"]
  S2 --> S3["S03 모델별 운영 설정 반환"]
 end
 subgraph VARIANT["90-operations/analysis_variant.py"]
  V01["A00.V01 완료 Evaluation·태그 확인"] --> V02["A00.V02 Evaluation 동일 복사·원본 해시 동결"] --> V03["A00.V03 기존 분석 없는 새 run"]
 end
 subgraph STARTUP["90-operations/execution_start.py"]
  L01["A00.L01 동결한 실제 모델·effort 읽기"] --> L02["A00.L02 작업·요청·동시 수 출력"] --> L03["A00.L03 Python/LLM 단계 실행"]
 end
 V03 --> L01
 subgraph RESTART["90-operations/analysis_restart.py"]
  R01["A00.R01 중지·종료·Evaluation 검사"] --> R02["A00.R02 이전 분석 전체·해시 보존"] --> R03["A00.R03 새 config·동일 입력의 새 요청 동결 / LLM 0건"]
  R01 -->|실패| RF["원기록 유지·오류 반환"]
 end
 subgraph SEQUENCE["90-operations/analysis_sequence.py"]
  Q01["A00.Q01 승인된 run 목록·현재 PID·선후 관계 등록; 선행 지정 없으면 첫 run 즉시 진행"] --> Q00["A00.Q00 선행 run 지정 시 analysis·full_pipeline 모두 COMPLETE까지 대기"] --> Q02["A00.Q02 Evaluation 완료·분석 중지 확인"] --> Q03["A00.Q03 Analysis pipeline 실행"] --> Q04{"A00.Q04 결과"}
  Q04 -->|완료| Q05["실제 완료 기록·다음 run"] --> Q02
  Q04 -->|오류·미확인| Q06["원기록 보존·순서 중단"]
 end
 subgraph DOC["90-operations/run_documentation.py"]
  D01["D01 render: 저장 config·state·runtime output_budget 읽기"] --> D02["D02 현행 루트 사용법 삽입"]
  D02 --> D03["D03 단계 템플릿 + 실제 상태로 README 생성"]
 end
 subgraph CONTROL["90-operations/execution_control.py"]
  C01["A00.C01 pause: 해당 실행기 종료·부분 출력 보존"] --> C02["A00.C02 resume-analysis: 승인·중지·Evaluation 완료 확인"] --> C03["A00.C03 미확인 시도 보존·Analysis만 대기 해제 / 모델 호출 0건"]
  C02 -->|실행 중·미승인| CF["재개 거절"]
  C03 --> C04["A00.C04 retry-analysis-requests: 동결 manifest·지정 ID·종료 확인·한 번 재호출 승인"] --> C05["A00.C05 LLM: 승인 ID만 호출·동일 스키마 검사"] --> C06["A00.C06 전체 상태 재집계·다른 오류와 미실행 요청 보존"]
  C04 -->|누락 ID·종료 미확인| CF
 end
 C03 --> Q03
 T["현행 사용법·단계 README 템플릿"] --> D02
 T --> D03
 D03 --> O["run 루트·각 단계 README"]
 F["run의 동결 정의·prompt·schema"] -.->|수정하지 않음| D01
```

DOC의 순서는 문서 생성입니다. STARTUP은 실행 직전 정보를 출력하며, Analysis 순서 실행은 해당 pipeline의 LLM 단계를 호출합니다. 이미 실행 중인 Python 프로세스에는 새 함수가 자동으로 로드되지 않으므로 코드 변경을 적용하기 위해 실험을 중복 실행하지 않습니다.
