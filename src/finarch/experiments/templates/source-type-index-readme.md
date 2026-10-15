# {run} · 원천 유형별 검토

완료된 1,080문항 실험을 동결된 준비 자료의 `source_id`로 네 갈래로 나누었습니다. 새 모델 호출·점수 수정·의미 정답 판정 없이 저장된 34,560응답과 A02 관찰을 재집계했습니다. `build.log`에 처리 결과를 남겼습니다.

1. [실험 뷰어의 A02 관계 비교](http://127.0.0.1:8894/?run={run}&tab=conditions)에서 **원천 유형**을 선택하면 유형별 8변형×4조건, 응답 상태, 문항과 관찰을 화면에서 바로 봅니다. [A03 연구 해석](http://127.0.0.1:8894/?run={run}&tab=reports)에도 네 보고서 입구가 있습니다.
2. [overview.md](overview.md)에서 유형 간 기술 통계를 대조하고, [source-type-index.json](source-type-index.json)에서 네 유형의 문항·응답·관찰 수와 원천 파일 해시를 확인합니다.
3. 각 폴더의 `README.md` → `review.md` → `summary.json` → `cases.jsonl` 순서로 읽습니다.
4. 같은 화면의 전체 A03 주제 묶음은 유형별로 새로 검증한 결론이 아니므로, 연결 관찰 수와 구분해서 읽습니다.

|원천 유형|보고서|
|---|---|
|FinQA|[exp-001-luna-FinQA](exp-001-luna-FinQA/README.md)|
|TAT-QA|[exp-001-luna-TAT-QA](exp-001-luna-TAT-QA/README.md)|
|FinanceMath|[exp-001-luna-FinanceMath](exp-001-luna-FinanceMath/README.md)|
|FinanceReasoning|[exp-001-luna-FinanceReasoning](exp-001-luna-FinanceReasoning/README.md)|

유형 이름은 FinanceReasoning 선별 집합에 남은 원천 계보입니다. 서로 다른 난도·문항 구성·제작 당시 외부지식 사용 표기가 섞여 있으므로 유형 간 차이는 인과효과가 아닙니다.
