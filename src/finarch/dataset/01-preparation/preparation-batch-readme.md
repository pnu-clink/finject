# Preparation 실행 기록

읽는 순서: `input-selection.json` → `plan.json`·`config.json`·`schedule-settings.json` → `01-preparation/schedule-state.json` → 문항별 `run.json`과 차수 폴더 → `01-preparation/summary.json`·`review-gate.json`.

현재 모델 프로필은 config.json이 가리키는 TOML과 용도별 hyperparameter 설정에서 읽습니다. 실제 요청의 모델·프롬프트·스키마는 각 LLM 입력 기록에서 확인합니다. 새 실행은 과거 run의 LLM 응답을 복사하지 않습니다.

공통 viewer에서 이 실행을 선택해 실제 산출물을 확인합니다. Preparation의 자동 검사 통과는 run.json의 PASS가 기준입니다. Generation은 별도 명령으로 실행합니다. `timing.json`과 로그에는 실행 명령·시각·소요 시간이 저장됩니다.

## 병렬 처리 기록
API 작업은 `shared.api.concurrency`(현재 200)로 고정하며 CPU에 따라 늘리지 않습니다. 남은 대상이 적으면 그 수만 실행합니다. 같은 프로세스의 실제 HTTP 요청에도 동일한 상한을 적용합니다. CLI는 기존 CPU 기반 설정을 사용합니다.

`schedule.lock`을 소유한 스케줄러 하나가 queue·summary·review-gate를 기록합니다. 개별 worker는 자기 문항 폴더에만 산출물을 씁니다. `queue.json`은 현재 동시 처리 현황, `queue.jsonl`은 변경 이력입니다.

## 중단 후 재개

`--run <이 실행 폴더> --resume`으로 pending_ids·running_ids를 다시 등록합니다. `--cases`나 JSON 배열을 담은 `--cases-file`로 특정 ID만 지정할 수도 있습니다. 해당 문항의 이전 폴더는 `restart-history/NNN-preparation/test-xxxx`에 보존하고, 같은 번호의 `01-round/01-source`부터 새로 시작합니다. 다른 완료 문항은 유지합니다. 재개와 별개로 정상 실행 중 오류 피드백에 따른 2·3차 반복은 유지합니다.
