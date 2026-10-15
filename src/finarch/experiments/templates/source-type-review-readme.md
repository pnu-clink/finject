# {run} · {name} 원천 유형별 검토

완료된 동일 실험의 원본 {count}문항만 분리해 저장 응답과 문항별 관찰을 재집계했습니다. 새 실험이나 모델 호출이 아닙니다.

1. [실험 뷰어](http://127.0.0.1:8894/?run={run}&tab=conditions&source_type={name})의 **A02 관계 비교**에서 이 유형의 수치·null·형식 상태와 문항을 화면에서 확인합니다. **A03 연구 해석 → 원천 유형별 검토**에서 이 보고서도 열 수 있습니다.
2. [review.md](review.md)에서 문항 구성, 원본 일치, 변형·조건 차이, RQ별 해석 범위를 읽습니다.
3. [summary.json](summary.json)은 모든 변형·지시·추론 설정의 분모·형식 상태·숫자/null을, [cases.jsonl](cases.jsonl)은 원천 ID와 A02 관찰 ID를 기록합니다.
4. [상위 README](../README.md)와 [source-type-index.json](../source-type-index.json)의 원천 해시·전체 분할 검사를 확인합니다.

원본 외부지식 사용 표기는 private 제작 기록의 유형별 집계입니다. 모델이 실제 외부지식을 사용했는지를 뜻하지 않습니다. 원응답·점수·A02/A03 원문은 수정하지 않았습니다.
