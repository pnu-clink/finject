# {output_name}

전체 {input_count}문항의 원문과 7유형 합본입니다. `{base_run}`에서 CodeTAT-QA {replaced_count}문항을 `{replacement_run}`의 결과로 교체했습니다. 7유형 전체 자동 PASS 문항은 **{after_all_seven_pass}개**입니다. 자동 PASS와 사람 승인은 별개입니다.

## 데이터 읽기

1. [results/README.md](results/README.md): 전체 문항, 실패·미실행 기록 포함.
2. [results/all-seven-pass/README.md](results/all-seven-pass/README.md): 7유형 모두 통과한 최종 선정본.
3. 각 폴더의 `00-input.json`과 `01~07` 유형별 JSON을 같은 `id`로 연결합니다.

[데이터셋 화면](http://127.0.0.1:8893/?run={output_name})에서 실제 질문·원문·7유형 변형 본문을 봅니다. 기존과 같은 검증 화면에서 Preparation 01~07, Generation 각 유형의 01~05 단계, Python 코드·그래프·원응답·검증 근거·사람 판정을 확인합니다. 필터와 단축키도 기존 기능을 사용합니다.

## 파일과 로그

`results/manifest.json.row_source_runs[id]`는 해당 행의 원천 run입니다. 행 안의 `source`, `result`, `edit_provenance`, `inverse_review_ref` 경로는 그 원천 run 기준입니다. `01-preparation/`, `02-generation/`에는 선택된 원천 문항의 실제 단계 기록을 독립적으로 복제했습니다. 파일을 편집해도 원천 run 파일은 바뀌지 않습니다. 복제는 새 LLM 호출이나 pipeline 재실행이 아닙니다.

[작업 로그](../../../log/dataset-concat/{output_name}/README.md)에 교체 기록·원천 해시·질문 표현 차이·검사 결과를 보존합니다. 데이터셋 화면에는 보고서를 표시하지 않습니다.

## 실행 방법

```shell
PYTHONPATH=src .venv/bin/python -B -m finarch.dataset.03-release.concat_results \
  --base-run reports/run/{base_run} \
  --replacement-run reports/run/{replacement_run} \
  --output-run reports/run/{output_name} \
  --source-prefix CodeTAT-QA-
```

기존 출력 폴더는 덮어쓰지 않습니다. LLM 호출은 없습니다.
