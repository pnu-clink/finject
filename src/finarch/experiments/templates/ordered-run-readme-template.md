# {run_id}

풀이 수집: **{status}** · 원본 {originals}개 · 변형 {variants}개. 풀이 수집 완료와 내용 분석 완료는 별개입니다.

## 읽는 순서

1. [00 Input](00_input/README.md): public의 질문·본문·precision, private의 평가 참조.
2. [01 Evaluation](01_evaluation/README.md): 준비 → 요청 → LLM 풀이 → 형식 검사·수치 평가.
3. [02 Analysis](02_analysis/README.md): 결과 취합 → 관계 비교 → 연구 해석.

`config.json`의 `evaluation`은 대상 모델 실험, `analysis`는 API/Codex 분석 설정입니다. 실제 실행은 이 사본을 사용하며, 첫 분석 전에 별도로 동결한 `02_analysis/config.json`이 있으면 Analysis는 그 설정을 사용합니다. 원본 설정 변경으로 실행 중인 조건이 바뀌지 않습니다.

- [설정](config.json) · [계획](01_evaluation/02_request/plan.json) · [동결 파일 해시](manifest.json)
- [진행 상태](state.json) · [실행 명령·처리 현황](pipeline.log) · [상세 이벤트](events.jsonl)
- [풀이 수집 보고서](01_evaluation/04_validation/REPORT.md)

LLM 풀이 입력은 public에서만 구성합니다. private와 분석 결과는 대상 모델에게 전달하지 않습니다. 형식 통과는 정답·논리 타당성과 다릅니다. 분석 결과를 사용자에게 보여드리고 개선안을 합의한 후에만 후속 실험에 반영합니다.

`private.jsonl`에 `original_external_knowledge`가 있으면 원본 제작 시 확인된 외부지식 사용 분류입니다. 변형을 별도로 재판정한 값이나 풀이 모델의 사용 여부가 아닙니다. `used=false`는 확인 조건 미충족이며 비사용의 증명이 아닙니다. 이 값은 A01·A02·A03 분석에만 전달합니다.

공통 실험 뷰어에서 이 실행을 선택합니다. 결과 폴더마다 별도 HTML을 만들지 않습니다.

## 사용법과 재개

프로젝트 루트에서 이 실행을 재개하려면 다음 명령을 사용합니다. 새 실험을 만들 때만 `prepare`를 사용합니다.

```sh
RUN_PATH="{run_path}"
PYTHONPATH=src .venv/bin/python -u -B -m finarch.experiments.pipeline run --evaluation-only --run "$RUN_PATH"
```

이 명령은 동일 Batch ID를 조회·수집하고 E04 검사 후 Analysis 전에 끝납니다. 이미 pipeline이 실행 중이면 추가 실행하지 않습니다. 분석을 실행하기로 정한 경우에는 같은 명령에서 `--evaluation-only`를 빼면 A01 → A02 → A03가 이어집니다. 분석용 제작 메타와 동결된 분석 설정이 준비되어 있어야 합니다. 일시 중지 기록은 이 명령만으로 해제되지 않습니다.

```sh
tail -f "$RUN_PATH/pipeline.log"
PYTHONPATH=src .venv/bin/python -u -B -m finarch.experiments.pipeline report --run "$RUN_PATH"
```

`report`는 저장된 결과의 수집 보고서를 갱신하며 모델 호출 0건입니다. 제공자 처리 건수, 로컬 수집 건수, 형식 유효 건수는 구별합니다. E03 비용·실행의 Python 로그와 진행 화면은 [이 run의 실험 뷰어](http://127.0.0.1:8894/?run={run_id}&tab=costs)에서 확인합니다. 단계별 사용법은 위 읽는 순서의 README를 따릅니다.
