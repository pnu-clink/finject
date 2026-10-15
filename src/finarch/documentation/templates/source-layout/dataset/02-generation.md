# Generation 단계 제어

## 시작 프로그램

다건 Generation의 시작 프로그램은 `src/finarch/dataset/02-generation/generate_schedule.py`입니다. 기존 run에서 Preparation 진입 기준을 통과한 입력을 읽어 7유형 생성과 차수별 재시도를 관리합니다.

저장소 루트에서 실행합니다. 아래 `PATH_TO_EXISTING_RUN`은 실제 run 경로로 바꿔야 하는 자리표시자입니다.

```sh
PYTHONPATH=src .venv/bin/python -B -m finarch.dataset.02-generation.generate_schedule --run PATH_TO_EXISTING_RUN
```

기본 최대 차수는 hyperparameter의 `generation.schedule.max_rounds`를 읽습니다. 기존 Generation이 중단된 경우 같은 명령에 `--resume`을 추가합니다. 완료된 Generation의 재시작은 거절됩니다. 일반 전체 실행에는 `--cases`를 사용할 수 없으며, 문항·유형 선택은 단계 선택 옵션과 함께 사용하는 별도 경로입니다.

실제 다건 경로: `generate_schedule.run` → `generate_run.process` → 각 단계의 `stage.py`. 정상 순서는 01-perturbation → 02-generate-text → 03-validation → 05-human-review이며, 실패 시 04-exception-handler로 분기합니다. 다음 차수는 재시도 가능한 실패 유형을 대상으로 하며 VALUE/SOURCE 의존성도 처리합니다.

실행 설정은 run의 `config.json`, 모델·effort는 선택된 프로필 정의에서 읽습니다. 동시 처리·최대 차수·목적별 모델 선택은 hyperparameter 설정에 연결됩니다. 결과는 같은 run의 `02-generation`에 저장합니다. 검토 자료 생성까지의 제작 구간이며 사람의 실제 판정과 Evaluation·Analysis는 실행하지 않습니다.

[문서의 단계·요구·실행 흐름](../../../../docs/01-dataset/02-generation/README.md) · [전체 소스 구조](../../../../docs/01-dataset/90-operations/05-source-layout.md)

이 폴더는 위 문서 단계의 실행 코드를 소유합니다. 결과의 물리 경로는 기존 run 계약을 따릅니다.

|파일|역할|
|---|---|
|[generate_run.py](generate_run.py)|Generate seven variants from human-approved inputs with bounded feedback rounds.|
|[generate_schedule.py](generate_schedule.py)|다건 실행 시작점. 문항·유형·차수·재시도와 공유 기록 관리|
|[stage_execution.py](stage_execution.py)|Compatibility entry for callers of the former stage dispatcher.|

하위 단계: [01-perturbation](01-perturbation/README.md) · [02-generate-text](02-generate-text/README.md) · [03-validation](03-validation/README.md) · [04-exception-handler](04-exception-handler/README.md) · [05-human-review](05-human-review/README.md)
