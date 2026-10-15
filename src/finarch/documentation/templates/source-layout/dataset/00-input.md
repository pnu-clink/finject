# 입력 준비

## 시작 프로그램

FinanceReasoning 배포본 전체의 시작 프로그램은 `full_finance.py`입니다. 원천 종류에 따라 아래 기존 진입점을 선택합니다. 이 단계는 LLM을 호출하지 않습니다.

|입력 대상|시작 프로그램|받는 인자·처리|
|---|---|---|
|FinanceReasoning 전체|`src/finarch/dataset/00-input/full_finance.py`|`--catalog`, `--output`. easy → medium → hard 원천 해시 확인·제외·공통 입력 생성|
|TAT-QA 전체|`src/finarch/dataset/00-input/tatqa_full.py`|출력 폴더를 위치 인자로 받음. `config/source-catalog.json`의 TAT-QA 원천 사용|
|일반 표본 준비|`src/finarch/cli.py prepare` → `00-input/build.py`|`--sources`, `--output`, `--seed`, `--total` 또는 `--per-source`|

저장소 루트에서 실행합니다. 아래 `PATH_TO_...`는 실제 경로로 바꿔야 하는 자리표시자이며, 새 출력 폴더를 지정합니다.

```sh
PYTHONPATH=src .venv/bin/python -B -m finarch.dataset.00-input.full_finance --catalog PATH_TO_FINANCE_CATALOG --output PATH_TO_NEW_INPUT_FOLDER
```

Finance 전체 catalog에는 `finance-easy`, `finance-medium`, `finance-hard` 세 원천이 순서대로 있어야 합니다. TAT-QA를 포함한 원천 목록을 그대로 전달하면 거절됩니다. 출처를 한정할 때는 `--hyperparameter PATH_TO_HYPERPARAMETER_JSON`을 추가합니다. `input.source_prefix`로 출처를 고르고 `input.id_map_path`로 기존 입력의 raw_id → id 대응을 보존하며 `input.expected_count`로 최종 수량을 검사합니다. 원천·Q/C/A는 현재 어댑터로 새로 읽고 이전 LLM 결과는 재사용하지 않습니다.

내부 경로: 원천 선정 → `adapters.py` → `content.py` → JSON 본문이면 `json_context.py` → 입력 스키마 검사 → `data/prepared/...` 산출물. `check_json_contexts.py`는 별도 점검 도구이고 제작 시작점이 아닙니다. 다음 01에는 완성된 `input.json`을 전달합니다.

[문서의 단계·요구·실행 흐름](../../../../docs/01-dataset/00-input/README.md) · [전체 소스 구조](../../../../docs/01-dataset/90-operations/05-source-layout.md)

이 폴더는 위 문서 단계의 실행 코드를 소유합니다. 결과의 물리 경로는 기존 run 계약을 따릅니다.

|파일|역할|
|---|---|
|[adapters.py](adapters.py)|Explicit adapters for two source schemas. Source programs are never executed.|
|[build.py](build.py)|Freeze inputs from hash-verified local sources; do not infer generation success.|
|[content.py](content.py)|Common original-content structure and exact Unicode character locations.|
|[dataset_survey.py](dataset_survey.py)|Bundle a documented dataset survey for the shared viewer without model calls.|
|[full_finance.py](full_finance.py)|Prepare the complete pinned distribution; inspect source ASTs without execution.|
|[tatqa_full.py](tatqa_full.py)|Prepare all local TAT-QA arithmetic questions without context-only deduplication.|
