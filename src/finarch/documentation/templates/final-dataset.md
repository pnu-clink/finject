# {name} · Human annotation 통과 최종 데이터셋

`dataset.jsonl`은 한 줄에 원문 1개와 7유형의 실제 질문·본문, 자동 검사, 최종 통과 상태를 담습니다. 최종 문항은 **{cases}건**입니다. 선정 기준은 기존 제작 선정 조건을 충족하고, 두 평가자가 7유형 모두에 저장된 APPROVED 판정을 남긴 문항입니다. 최종 배포 형식에서 원문과 7유형의 `annotation`은 모두 `{"status": "PASS"}`만 기록합니다. 원문의 PASS는 제작 검사 통과를 나타내며, 원문에 별도 human annotation을 수행했다는 뜻은 아닙니다. 평가자별 상세 기록은 보존된 원천 자료에 남겨둡니다.

|출처|개수|최종 ID|
|---|---:|---|
|FinanceReasoning|{finance_cases}|id-0001 ~ id-1071|
|TAT-QA|{tatqa_cases}|id-1072 ~ id-1354|

## 파일과 읽는 순서

1. `manifest.json`: 선정 기준, 출처별 개수, 파일 해시와 원천 자료 정보.
2. `dataset.jsonl`: 원문 `original`과 정해진 순서의 `variants` 7유형. 각 항목의 `annotation`은 `{"status": "PASS"}`입니다. 평가자별 `ratings`는 포함하지 않습니다.
3. [연결표](../{connection_filename}): `final_id`로 찾아 `source_dataset`, `source_run`, `source_case_id`, `source_file`, `source_line_number`를 확인합니다. 예를 들어 `id-0001`은 FinanceReasoning의 `{first_finance_case}`, `id-1072`는 TAT-QA의 `{first_tatqa_case}`입니다.
4. `dataset.schema.json`: 문항 구조와 ID·내용 해시·annotation 연결 규칙. `events.jsonl`: 실제 취합 및 검사 결과.

최종 ID는 출처별 원래 문항 번호의 오름차순으로 부여합니다. 상위 `id`, `source_input.id`, 각 항목의 `item_id`를 함께 변경했습니다. 원래 ID와 항목 ID는 `metadata.publication_source` 및 별도 연결표에 보존합니다. 질문·본문·정답은 변경하지 않았습니다. 원문 정답을 변형 문항의 정답으로 가정하지 않습니다.

원천 합본: FinanceReasoning은 `data/generated/20261003-concat-002/dataset.jsonl`, TAT-QA는 `data/generated/20261003-003/dataset.jsonl`입니다. 원천 합본은 유지합니다. 이 작업은 저장 데이터 취합이며 LLM 호출은 없습니다.

원래 단계 자료는 [FinanceReasoning 공통 뷰어](http://127.0.0.1:8893/?run=20261003-concat-002)와 [TAT-QA 공통 뷰어](http://127.0.0.1:8893/?run=20261003-003)에서 연결표의 `source_case_id`로 확인합니다. 이 README는 `src/finarch/documentation/templates/final-dataset.md`에서 생성했습니다.
