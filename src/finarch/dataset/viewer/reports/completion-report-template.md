# {run} 자동 결과 리포트

원문 {input_count}문항 · Preparation 승인 {approved}문항 · 제외 {excluded}문항 · 판정 대기 {pending}문항.

{tables}

통과·실패는 차수까지 누적한 자동 검사 결과입니다. 이전 차수에서 유지한 통과는 새 호출 성공으로 세지 않습니다. 미실행·미평가는 통과가 아닙니다. Preparation은 문항, Generation은 문항×유형 단위입니다. 최종 사람 판정은 수행하지 않았습니다.

[뷰어에서 차수별 원인과 결과 확인](http://127.0.0.1:8893/?run={run}&report=completion) · [Generation 상세 결과](02-generation/RESULTS.md)

`completion-report.json`에는 문항별 1·2·3차 상태·실패 근거·원기록 위치가 있습니다. 보완 이력은 `01-preparation/repair-history`에 보존합니다. 각 차수의 실제 보완 지침과 원응답은 해당 Generation 폴더에서 확인합니다. 호출 취소·시간 초과는 내용 오류와 구분하여 JSON의 `execution_failures`에 표시합니다.
