# {run_name} · 실험 전달용 제작 결과

## 목적과 상태

제작 run `{source_run}`의 `results/`를 `{output}`에 바이트 동일 사본으로 정리했습니다. 원본·정답·변형 문장·검사 상태·명시적 사람 제외 기록은 변경하지 않았습니다. 기존 제작 실행 기록은 원래 run에 보존합니다. 이 폴더는 private 기준·제작 이력도 포함하므로 모델 공개 입력 자체가 아닙니다.

- 취합된 원본: **{originals}건**.
- 원본과 7변형 모두 자동 PASS인 집단: **{complete}문항군**.
- 7변형 전체 PASS 조건을 충족하지 않는 원본: **{incomplete}건**. 실패·미실행 등은 원상태로 보존합니다.
- 실험 입력 선택기는 현재 제작 상태·사람 제외·관찰·검사 해시를 다시 확인하고, 설정한 7변형 PASS 집단만 선정합니다.
- 자동 PASS는 사람 승인이나 의미 정답 확정과 다릅니다.

## 파일 역할과 읽는 순서

1. `prepared-results.json`: 원천 run·manifest 해시, 사본 파일 전체 해시, 자동 완료 집단의 ID와 범위.
2. `manifest.json`: 원천에서 보존한 선정 정책·행 수·상태·제외 근거·파일 해시.
3. `00-input.json`: 원본 Q/C와 private 참조 답·정밀도·외부지식 분류.
4. `01`~`07` 유형 JSON: 같은 ID에 연결된 생성 Q/C와 자동 검사 상태·변경 기록. 행 위치 대신 ID로 연결합니다.
5. `export-log.json`, `SOURCE-README.md`, 있을 경우 `revisions/`: 원천 취합·보강 기록과 원래 안내 문서.
6. `events.jsonl`: 이번 전달 기록. 모델 호출은 없습니다.

행의 `source`, `result`, 변경 이력·역산 참조 경로는 원천 run 또는 원천 manifest가 지정한 run을 기준으로 해석합니다. 데이터 폴더로 경로 기준을 바꾸지 않습니다. private 외부지식 분류·정답·변형 라벨·제작 기록은 대상 모델에 전달하지 않습니다.

## 만들기와 실험 연결

```shell
PYTHONPATH=src .venv/bin/python -B -m finarch.dataset.03-release.export_run_results \
  {source_run} --prepared-output {output}
```

새 폴더로만 전달하며 기존 폴더를 덮어쓰지 않습니다. `evaluation.schedule.dataset.source_run`은 제작 이력, `results_path`는 이 전달 폴더, `input_path`는 이 폴더의 `00-input.json`으로 지정합니다. 실험 준비·실행은 `finarch.experiments.pipeline`을 사용합니다. 현재 원천과 전달본 해시가 달라지면 호출 전에 중단합니다.

## 확인 화면

[원천 제작 결과 뷰어](http://127.0.0.1:8893/?run={run_name})에서 실제 문항·생성·검사·사람 판정을 확인합니다. 신규 Evaluation의 공개/비공개 동결 입력·요청·원응답은 [공통 실험 뷰어](http://127.0.0.1:8894/)에서 별도 experiments-run을 선택해 확인합니다. 이 폴더의 존재는 실험 실행 완료를 뜻하지 않습니다.

README는 `src/finarch/documentation/templates/prepared-generation-results.md`에서 생성합니다.
