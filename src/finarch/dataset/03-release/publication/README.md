# 전체 Generation 결과 단일 취합

시작 프로그램은 [consolidate.py](consolidate.py)입니다. 전체 Generation 종료 시 기존 [generate_schedule.py](../../02-generation/generate_schedule.py)가 호출하며 기존 full_pipeline.py도 그 경로를 사용합니다. 새 pipeline.py는 만들지 않습니다.

|파일|책임|
|---|---|
|[consolidate.py](consolidate.py)|완료 여부·최신 상태·원천 해시 확인, 전체 실패·Reject를 보존하는 JSONL·manifest·로그·템플릿 README, 내용이 연결된 annotation의 새 버전 취합|
|[schema.py](schema.py)|정확한 원문+7유형·내용 해시·안정된 ID·평가자 rating 연결 검사|

출력은 `data/generated/<run-id>/`입니다. 한 줄에 원문과 7유형의 실제 Q/C를 넣습니다. 정답 메타정보는 원문에 저장하며 이를 변형의 정답이라고 간주하지 않습니다. 실패·Reject를 보존하는 전체 취합과 7유형 통과·Reject 없음 선정을 구분하고, 미검토 annotation을 Accept로 바꾸지 않습니다.

기존 합본이 동일하면 바이트를 유지합니다. 원천·annotation이 바뀌면 새 출력 폴더를 지정해야 하며 과거 합본을 덮어쓰지 않습니다. 모든 입력을 다시 해시 확인한 뒤 임시 폴더를 확정합니다. 부분 실행·실패 해석·재검토 경로에서는 자동 취합하지 않습니다.

```shell
# 완료된 과거 run도 같은 프로그램으로 취합합니다. LLM 호출 없음.
PYTHONPATH=src .venv/bin/python -B -m finarch.dataset.03-release.publication.consolidate \
  --run reports/run/20261003-003
```

공통 viewer의 **생성 데이터 합본** 버튼은 이 저장 파일의 해시·실제 Q/C를 확인합니다. 별도 결과 HTML이나 실험 실행은 만들지 않습니다. 상세 흐름·실패 경로는 [결과 전달 README](../../../../../docs/01-dataset/03-release/README.md)의 R06.1~5를 따릅니다.
