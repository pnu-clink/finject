# Preparation 단계 제어

## 시작 프로그램

다건 Preparation의 시작 프로그램은 `src/finarch/dataset/01-preparation/prepare_schedule.py`입니다. 준비된 `input.json`과 실행 설정을 받아 대상 문항·차수·재시도를 관리합니다.

저장소 루트에서 실행합니다. 아래 `PATH_TO_...`는 실제 경로로 바꿔야 하는 자리표시자입니다.

```sh
PYTHONPATH=src .venv/bin/python -B -m finarch.dataset.01-preparation.prepare_schedule --input PATH_TO_INPUT_JSON --config PATH_TO_RUN_CONFIG --cases-file PATH_TO_CASE_IDS_JSON
```

`--cases-file`은 `["test-0001", "test-0002"]` 형태의 대상 ID 목록입니다. `--cases`로도 지정할 수 있으며 두 옵션을 함께 쓰지 않습니다. 대상을 생략하면 입력 전체를 처리합니다. 실행 없이 대상·설정을 확인하려면 같은 명령에 `--plan-only`를 추가합니다.

기존 run의 중단 문항을 재개할 때는 다음 경로를 사용합니다. 완료 문항은 자동 재개 대상에서 제외되며, 미완료 문항은 원문 단계부터 다시 시작합니다.

```sh
PYTHONPATH=src .venv/bin/python -B -m finarch.dataset.01-preparation.prepare_schedule --run PATH_TO_EXISTING_RUN --resume
```

실제 다건 경로: `prepare_schedule.main` → `run_selected` → `run_case_rounds` → `prepare_run.run` → 각 단계의 `stage.py`. 정상 순서는 01-source → 02-review → 03-calculation → 04-graph → 05-verification → 07-human-review이며, 실패 시 06-exception-handler로 분기합니다. `preparation_pipeline.py`는 별도 `prepare_batch/run_case` 경로를 가진 내부 모듈이며, 현재 다건 CLI의 시작 프로그램이 아닙니다.

`--config`는 실행·프로필 경로 설정이고, 동시 처리·재시도·목적별 모델 선택은 hyperparameter 설정에서 읽습니다. 실행 전 선택된 프로필의 실제 `model`과 `effort`를 확인합니다. 결과는 `reports/run/<run>/01-preparation`에 저장하며 02는 해당 run을 입력으로 받습니다. 사람 검토 자료 생성과 사람의 실제 판정은 별개입니다.

스케줄러는 유효 실행 설정을 `01-preparation/runtime-config.json`으로 저장하여 worker에 전달합니다. 이 파일에는 `run_phase=preparation`, 절대 `profiles_path`, 해당 run의 `hyperparameter_path`가 포함됩니다. worker가 모델 선택 단계나 모델 버전을 다시 추측하지 않도록 하는 설정 기록이며, 실행 중 개별 worker가 이 파일을 갱신하지 않습니다.


[문서의 단계·요구·실행 흐름](../../../../docs/01-dataset/01-preparation/README.md) · [전체 소스 구조](../../../../docs/01-dataset/90-operations/05-source-layout.md)

이 폴더는 위 문서 단계의 실행 코드를 소유합니다. 결과의 물리 경로는 기존 run 계약을 따릅니다.

|파일|역할|
|---|---|
|[preparation_pipeline.py](preparation_pipeline.py)|Execute source audit before calculation and stop at human review.|
|[preparation_preflight_retry.py](preparation_preflight_retry.py)|Retry an entirely uncalled batch after native-control verification succeeds.|
|[prepare_queue.py](prepare_queue.py)|Scheduler-owned case IDs. Interrupted cases restart at source without feedback reuse.|
|[prepare_run.py](prepare_run.py)|Execute one preparation case within an explicit stage range.|
|[prepare_schedule.py](prepare_schedule.py)|유효 runtime-config 저장·worker 전달, 문항·차수·재시도 관리, 결과·공유 파일 취합.|
|[repair_failed_preparation.py](repair_failed_preparation.py)|Give previously failed Preparation cases one recorded repair opportunity.|
|[stage_execution.py](stage_execution.py)|Compatibility entry for callers of the former stage dispatcher.|

하위 단계: [01-source](01-source/README.md) · [02-review](02-review/README.md) · [03-calculation](03-calculation/README.md) · [04-graph](04-graph/README.md) · [05-verification](05-verification/README.md) · [06-exception-handler](06-exception-handler/README.md) · [07-human-review](07-human-review/README.md)
