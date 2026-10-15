# fin-arch

금융 원문에서 값 충돌·출처 조건·관계 모순·필수 근거 부재를 구성하는 데이터셋 제작 프로젝트입니다. 제작과 대상 모델 실험을 분리합니다.

## Dataset Construction

**기본 데이터 → adapter 연결 → 00-input → 01-preparation → 02-generation** 순서로 진행합니다. 아래 명령은 저장소 루트에서 실행하며, `PATH_TO_...`는 실제 경로로 바꿉니다. 입력 출력 폴더는 새 폴더를 사용하고, 01이 만든 run을 02에 그대로 전달합니다. 본문은 공통 절차를 설명하며, 원천별 실행 명령과 특정 데이터셋의 설정은 뒤쪽 [추가 설명·특정 사례](#추가-설명특정-사례)에 모았습니다.

### 1. 기본 데이터셋을 만든다

원본 질문(Q), 본문(C), 정답(A)을 갖춘 원천 파일을 [data/raw](data/raw/README.md)에 준비합니다. 원본은 보존하고, source catalog에 파일 경로·SHA-256·출처 URL·버전(commit)·adapter 이름을 기록합니다. 원천 파일과 catalog는 00의 입력이며, LLM의 이전 생성 결과를 원천으로 사용하지 않습니다.

### 2. 필요한 경우 adapter를 생성하고 연결한다

기존 원천 형식이면 기존 adapter를 사용합니다. 새 형식이면 해당 원천의 Q/C/A를 공통 입력 스키마로 바꾸는 adapter를 작성하고, [adapters.py](src/finarch/dataset/00-input/adapters.py)에서 호출하도록 연결합니다. **현재 파일명은 `adapter.py`가 아니라 `adapters.py`입니다.** 새 adapter 이름은 catalog와 실제 00 시작 프로그램의 분기에도 등록해야 합니다.

adapter는 [content.py](src/finarch/dataset/00-input/content.py)로 본문을 구성합니다. JSON 본문은 [json_context.py](src/finarch/dataset/00-input/json_context.py)로 표 형태로 변환합니다. 이 단계는 입력 구조를 맞추며 정답을 수정하지 않습니다.

### 3. 00-input을 실행한다: 원천을 공통 입력으로 준비

원천 목록과 선정 범위를 받아 원천 해시 확인 → 대상 선택·제외 → adapter 변환 → 입력 스키마 검사를 진행합니다. 기존 [00-input 시작 프로그램 안내](src/finarch/dataset/00-input/README.md)에서 대상과 선정 방식에 맞는 진입점을 선택합니다.

원천별 표본 준비에는 공통 진입점 [cli.py prepare](src/finarch/cli.py)를 사용합니다. 아래 `COUNT_PER_SOURCE`는 원천별 선정 수, `SELECTION_SEED`는 선정 순서를 재현할 설정입니다.

```shell
# catalog에 등록된 각 원천에서 표본을 골라 공통 입력 생성
PYTHONPATH=src .venv/bin/python -B -m finarch.cli prepare \
  --sources PATH_TO_SOURCE_CATALOG_JSON \
  --output PATH_TO_NEW_INPUT_FOLDER \
  --per-source COUNT_PER_SOURCE \
  --seed SELECTION_SEED
```

전체 선정이나 출처 한정은 원천별 시작 프로그램의 인자를 사용합니다. 이 경우의 실행 명령과 추가 설정은 뒤쪽 [추가 설명·특정 사례](#추가-설명특정-사례)를 확인하십시오.

산출물 읽는 순서: 출력 폴더의 `README.md` → 선정·제외·원천 이력을 담은 로그와 manifest → `input.json`(다음 단계 입력). `provider-records.json`도 같은 폴더에 함께 유지합니다. **00은 LLM을 호출하지 않습니다.**

### 4. 01-preparation을 실행한다: 원문 풀이·계산·그래프 검증

시작 프로그램은 [prepare_schedule.py](src/finarch/dataset/01-preparation/prepare_schedule.py)입니다. 00에서 만든 `input.json`을 전달합니다.

```shell
# 원문 검토 → LLM Python 풀이 → Python 실행·정답 대조 → 계산 그래프 → 검증
PYTHONPATH=src .venv/bin/python -B -m finarch.dataset.01-preparation.prepare_schedule \
  --input PATH_TO_NEW_INPUT_FOLDER/input.json \
  --config PATH_TO_LLM_CONFIG_JSON
```

`config.json`에는 실제 실행 설정과 `profiles_path`, `hyperparameter_path`를 지정합니다. 모델·effort는 해당 프로필과 hyperparameter에서 선택하므로, 특정 버전을 재현할 때는 버전이 포함된 모델·프로필을 명시합니다. 동시 처리·최대 차수도 hyperparameter로 전달합니다. 전체 입력을 처리하는 위 명령은 `--cases-file`이 필요하지 않습니다.

새 run은 `reports/run/YYYYMMDD-NNN`에 자동 생성되며, 마지막 출력의 `run` 값이 다음 단계에 전달할 경로입니다. 산출물은 그 run의 `01-preparation`에 저장됩니다. 읽는 순서: run의 `README.md` → `01-preparation/summary.json` → 각 문항의 `run.json`과 활성 차수의 원문·Python·그래프·검증 기록. 공통 [dataset viewer](viewer/dataset/README.md)에서 같은 run을 선택해 확인합니다. 자동 검증 통과와 사람의 검토 판정은 구별합니다.

### 5. 02-generation을 실행한다: 같은 run에서 7유형 생성

시작 프로그램은 [generate_schedule.py](src/finarch/dataset/02-generation/generate_schedule.py)입니다. 01이 완료된 run을 그대로 전달합니다.

```shell
# Preparation 진입 기준 확인 → 변경 계획 → 문장 생성 → 완성문 검증·재시도
PYTHONPATH=src .venv/bin/python -B -m finarch.dataset.02-generation.generate_schedule \
  --run PATH_TO_RUN_FROM_PREPARATION
```

현재 진입 기준은 Preparation 문항의 `run.json` 상태와 필수 산출물 검사입니다. 전체 대상의 처리가 끝나고 필수 자료가 유효해야 하며, 자동 PASS 문항만 Generation으로 넘어갑니다. FAIL/ERROR는 제외하고 미완료·자료 오류가 있으면 진입을 중단합니다.

같은 run의 `config.json`·hyperparameter·프로필을 읽어 IC-VALUE 앞/뒤, IC-SOURCE Type 1/2, IC-RELATION, EA-01/02를 생성합니다. 실패하면 04-exception-handler로 분기하며 다음 차수에는 재시도 가능한 실패 유형만 처리합니다. 결과는 `02-generation`에 저장되고 05-human-review에서 사람이 확인할 자료를 제공합니다. Evaluation·Analysis는 이 명령에 포함되지 않습니다.

산출물은 run의 `README.md`와 `02-generation/README.md`를 먼저 읽고, 공통 viewer에서 차수·문항·유형을 선택해 확인합니다. 특정 데이터셋의 실행 기록은 뒤쪽 [추가 설명·특정 사례](#추가-설명특정-사례)에 있습니다.

전체 Generation이 끝나면 `data/generated/<run-id>/dataset.jsonl`에 원문과 7유형의 실제 Q/C를 자동 취합합니다. 실패·Reject까지 보존하는 기록이며, 기존 7유형 통과·Reject 없음 선정 대상은 별도 표시합니다. 읽는 순서와 annotation 연결은 합본 폴더의 템플릿 README와 [결과 전달 안내](docs/01-dataset/03-release/README.md)를 확인하십시오. 공통 viewer의 **생성 데이터 합본** 버튼으로 실제 저장 내용을 읽을 수 있습니다.

## 대상 모델 실험 사용법

프로젝트 루트에서 다음 순서로 진행합니다. 데이터 생성은 dataset pipeline, 대상 모델 Evaluation·Analysis는 experiments pipeline이 담당합니다.

1. `config/experiments/config.toml`의 `evaluation.schedule.dataset.generated_path`에 `data/generated/<제작 run-id>`를 지정하고 모델·추론 설정을 확인합니다.
2. `config`로 설정을 확인하고 `prepare`로 실험 입력·요청을 동결합니다. 둘 다 모델 호출 0건이며 `prepare`가 새 run 경로를 출력합니다.
3. 출력한 run 경로로 `run --evaluation-only`를 실행합니다. Native Batch 제출·조회·수집·E04 검사까지 진행하고 Analysis 전에 끝납니다.
4. 실험 뷰어에서 해당 run을 선택하고 E03 비용·실행의 Python 로그 또는 진행 대시보드를 봅니다.
5. 분석용 메타가 준비되고 Analysis 실행을 정한 경우, Analysis 설정을 동결한 뒤 같은 run으로 `run`을 실행합니다.

```sh
PYTHONPATH=src .venv/bin/python -u -B -m finarch.experiments.pipeline config --config config/experiments/config.toml
PYTHONPATH=src .venv/bin/python -u -B -m finarch.experiments.pipeline prepare --config config/experiments/config.toml
RUN_PATH=reports/experiments-run/20261003-exp-004-tatqa-luna
PYTHONPATH=src .venv/bin/python -u -B -m finarch.experiments.pipeline run --evaluation-only --run "$RUN_PATH"
```

위 `RUN_PATH`는 실제 TAT-QA 실행 예시이며 새 `prepare`에서는 새로 출력된 경로로 바꿉니다. 실제 선정은 291원본 + 2,037변형이며 네 조건을 적용해 9,312요청을 만들었습니다. 이 수를 다른 데이터셋의 고정 요청 수로 사용하지 않습니다.

```sh
tail -f "$RUN_PATH/pipeline.log"
```

`pipeline.log`는 실제 Python 명령·단계·Batch 처리 건수를, `events.jsonl`은 상세 이력을 기록합니다. 같은 pipeline이 실행 중이면 중복으로 시작하지 않습니다. 기존 실험을 재개할 때 `prepare`를 다시 실행하면 다른 실험 폴더가 생깁니다.

[실험 소스 전체 사용법](src/finarch/experiments/README.md) · [단계별 설명](docs/02-experiments/README.md) · [설정 안내](config/experiments/README.md) · [실험 뷰어](http://127.0.0.1:8894/)

## 문서 읽는 순서

1. [전체 그림](docs/README.md)
2. [01 데이터셋 제작 파이프라인](docs/01-dataset/README.md): 입력 → Preparation → Generation → 결과 전달
3. 각 단계 폴더의 README에서 사용자 요구사항·세부 스텝·실제 코드·실패 경로 확인
4. [단계별 확인 사항](docs/01-dataset/99-open-issues.md)
5. [02 실험 문서](docs/02-experiments/README.md): Input → Evaluation → Analysis

파일과 폴더 번호는 요청 순번이 아닌 실제 run 진행 순서를 따릅니다. 현재 단계의 설명은 소속 단계 문서에 갱신하고, 과거 실행·설정·성과는 해당 실행 기록에 남깁니다.

## 실제 자료와 화면

- 원천: [data/raw](data/raw/README.md) · 준비 입력: [data/prepared](data/prepared/README.md)
- 제작 실행 기록: [reports/run](reports/run) · 대상 모델 실험 기록: [reports/experiments-run](reports/experiments-run)
- 공통 제작 뷰어: [viewer/dataset](viewer/dataset/README.md) · 실험 뷰어: [viewer/experiments](viewer/experiments/README.md)
- [프로젝트 대시보드](viewer/dashboard/03-project/README.md): 세션·업무 계층·최근 요청·미완료와 저장 실행 상태. [숫자 화면 2종](viewer/dashboard/README.md)은 실험 종합 현황과 문항 분석입니다.
- [서버 위젯](apps/server-widget/README.md): 메뉴 막대에서 네 조회 서버의 상태 확인·시작·중지·화면 열기

뷰어는 저장 자료를 읽으며, 문서의 ‘구현 확인’과 실제 실행·의미 검증 결과는 구별합니다. 이 README에서 특정 과거 run을 현재 실행 중이라고 선언하지 않습니다.

## 작업 기준과 과거 문서

[AGENTS.md](AGENTS.md)의 사용자 원칙과 [합의 기록](handoff/understanding-check.md)을 따릅니다. 이전 README와 docs는 [2026-09-23 보관본](archive/20260923-documentation-reorganization/README.md)에 있습니다. 현재 기본 읽기 대상은 위 새 문서입니다.

코드 폴더를 확인하려면 [소스 구조·파이프라인 대응](docs/01-dataset/90-operations/05-source-layout.md), 화면을 실행하려면 [네 서버 안내](viewer/README.md)를 읽습니다.

## 추가 설명·특정 사례

아래는 특정 원천과 과거 실행에 해당하는 추가 설명입니다. 앞의 공통 절차에서 해당 원천·선정 방식을 사용할 때 참고하십시오.

### FinanceReasoning 전체 입력 준비

시작 프로그램은 [full_finance.py](src/finarch/dataset/00-input/full_finance.py)입니다. [기존 catalog 예시](data/prepared/finance-reasoning/source-catalog.json)는 `finance-easy`, `finance-medium`, `finance-hard` 세 원천을 이 순서로 지정합니다.

```shell
# FinanceReasoning 전체의 원천 확인·제외·공통 입력 생성
PYTHONPATH=src .venv/bin/python -B -m finarch.dataset.00-input.full_finance \
  --catalog PATH_TO_FINANCE_CATALOG_JSON \
  --output PATH_TO_NEW_INPUT_FOLDER
```

이 프로그램의 선정 로그는 `selection-log.json`, manifest는 `selection-manifest.json`입니다. 원본 TAT-QA 전체 등 다른 원천은 [00-input 시작 프로그램 안내](src/finarch/dataset/00-input/README.md)의 해당 진입점을 사용합니다.

### CodeTAT-QA 출처 한정·기존 문제번호 보존

CodeTAT-QA는 위 FinanceReasoning 원천 안에서 선택합니다. 같은 `full_finance.py` 명령에 다음 인자를 추가합니다.

```shell
# hyperparameter에 정의한 출처·문제번호 대응·예상 수량 적용
PYTHONPATH=src .venv/bin/python -B -m finarch.dataset.00-input.full_finance \
  --catalog PATH_TO_FINANCE_CATALOG_JSON \
  --output PATH_TO_NEW_INPUT_FOLDER \
  --hyperparameter PATH_TO_HYPERPARAMETER_JSON
```

hyperparameter의 `input.source_prefix`는 `CodeTAT-QA-`입니다. 기존 문제번호를 보존하려면 `input.id_map_path`에 기존 `input.json`을 지정하고, `input.expected_count`로 예상 수량을 확인합니다. 구체적인 00 → 01 → 02 명령·로그·설정·결과는 [CodeTAT-QA 288건 실행 기록](reports/run/20261003-001-CodeTAT-QA-0917-002/README.md)을 참고하십시오. 새 실행에는 새 입력 폴더와 run을 사용합니다.

### 과거 작업 기록

- [Luna 실험 개선 기록](reports/run/20260923-experiment-improvement/README.md): 기존 결과·응답 계약·제한 실행·비교 보고
- [문서 재정리 기록](reports/run/20260923-dataset-documentation/README.md): 취합·원본 해시·이관표·화면 확인
