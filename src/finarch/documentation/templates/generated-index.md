# 생성 데이터 단일 합본

전체 Generation이 완료된 실행의 제작 기록입니다. 각 실행의 `dataset.jsonl` 한 줄에 원문과 7유형의 실제 Q/C·상태·원본 정답·출처가 포함되며 `reports/run` 없이 읽을 수 있습니다.

|실행|전체 문항|기존 7유형 통과·Reject 없음|안내|
|---|---:|---:|---|
|20261003-003 · TAT-QA|717|291|[README](20261003-003/README.md)|
|20261003-concat-002 · FinanceReasoning|2050|1260|[README](20261003-concat-002/README.md)|

전체 합본에는 실패·Reject도 남기며 `production_selection.eligible`이 기존 선정 조건 충족 여부입니다. 평가자 annotation은 초기 버전에 연결하지 않았습니다. 자동 PASS, 제작 판정, 평가자의 실제 검토를 구별합니다. 합본 폴더의 manifest·스키마·로그·README를 함께 전달하십시오.

[제작 결과 전달 경계](../../docs/01-dataset/03-release/README.md) · [공통 dataset viewer](http://127.0.0.1:8893/)
