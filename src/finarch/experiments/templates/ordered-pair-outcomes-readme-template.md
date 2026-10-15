# {run_id} · RQ1 원본–변형 대응 자료

## 읽는 순서

1. `summary.json`: 전체·네 조건·유형별 예정 쌍, 실패·미판정 및 분모.
2. `pairs.jsonl`: 같은 조건의 원본–변형 쌍과 실제 응답 파일 연결.
3. 각 행의 `original_result_path`·`variant_result_path`: 보존된 원응답과 검사 기록.

Q01 Pair Outcome Matrix는 같은 모델·풀이·추론 조건의 원본과 변형을 연결합니다. 가로축은 저장된 E04의 부호·정밀도를 반영한 원본 수치 정답 비교이며 단위·설명 의미는 별도 채점이 아닙니다. 세로축은 검증된 A02 `adaptation_success`입니다. 원본 정답/대응 성공은 ①, 원본 오답/대응 성공은 ②, 원본 오답/대응 실패는 ③, 원본 정답/대응 실패는 ④입니다.

`pairs.jsonl`의 `assessment_id`는 `../response-assessments.jsonl`의 실제 판정·근거에 연결됩니다. IC-value 앞/뒤, IC-source A/B, IC-relation, EA01/EA02별 건수를 모델·풀이·추론·원천 유형·private 답변 가능성 분류별로 집계합니다. 미수집·형식 실패·미검토·판정 불가는 예정 Pair에 보존하고 사분면 밖에 표시합니다. 사분면의 0은 확인된 배치 건수이며 미판정 문항의 실패를 뜻하지 않습니다.

실행 명령·집계 이벤트는 run 최상위 `pipeline.log`와 `events.jsonl`에 있습니다. 이 집계는 모델을 호출하거나 gold·응답·기존 점수·Analysis 완료 상태를 변경하지 않습니다.
