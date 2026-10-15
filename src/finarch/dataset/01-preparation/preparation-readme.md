# Preparation · 원본 검토

`reference-data.json`은 보정 전 참고 데이터, `data.json`은 검사 통과한 현재 작업 데이터입니다. `data-comparison.json`에 Q·C·A 각각의 변경 위치를 기록합니다. 뷰어는 기존 원천 비교 위에서 참고본을 왼쪽, 현재 데이터를 오른쪽에 표시합니다. 원천 자료는 보존하며 사람 승인 전에 Generation으로 넘기지 않습니다.

읽는 순서는 `01-source` 원문·출처 → `02-review-and-correct` 원문 검사 → `03-calculation` 코드와 정답 대조 → `04-graph` 계산 그래프 → `07-human-review` 사람 검토입니다.

원문 검사 실패 시 계산을 시작하지 않습니다. 자동 통과는 사람 승인이 아닙니다. 전체 문항의 사람 검토가 끝나야 승인된 자료를 Generation에서 읽을 수 있습니다. 승인 이후 자료가 변경되면 다시 검토해야 합니다.

`run.json`은 이 문항의 상태이며 `events.jsonl`은 실행 기록입니다. 생성되지 않은 단계는 실행하지 않은 단계입니다. 원본과 모델 원응답은 덮어쓰지 않습니다.
