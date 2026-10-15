# finject-20261007 · Human annotation 통과 최종 데이터셋

`dataset.jsonl`은 한 줄에 원문 1개와 7유형의 실제 질문·본문, 자동 검사, 최종 통과 상태를 담습니다. 최종 문항은 **1354건**입니다. 선정 기준은 기존 제작 선정 조건을 충족하고, 두 평가자가 7유형 모두에 저장된 APPROVED 판정을 남긴 문항입니다. 최종 배포 형식에서 원문과 7유형의 `annotation`은 모두 `{"status": "PASS"}`만 기록합니다. 원문의 PASS는 제작 검사 통과를 나타내며, 원문에 별도 human annotation을 수행했다는 뜻은 아닙니다. 평가자별 상세 기록은 보존된 원천 자료에 남겨둡니다.

|출처|개수|최종 ID|
|---|---:|---|
|FinanceReasoning|1071|id-0001 ~ id-1071|
|TAT-QA|283|id-1072 ~ id-1354|

## 파일과 읽는 순서

1. `manifest.json`: 선정 기준, 출처별 개수, 파일 해시와 원천 자료 정보.
2. `dataset.jsonl`: 원문 `original`과 정해진 순서의 `variants` 7유형. 각 항목의 `annotation`은 `{"status": "PASS"}`입니다. 평가자별 `ratings`는 포함하지 않습니다.
3. [연결표](../finject-20261007-connection-table.csv): `final_id`로 찾아 `source_dataset`, `source_run`, `source_case_id`, `source_file`, `source_line_number`를 확인합니다. 예를 들어 `id-0001`은 FinanceReasoning의 `test-0006`, `id-1072`는 TAT-QA의 `test-0004`입니다.
4. `dataset.schema.json`: 문항 구조와 ID·내용 해시·annotation 연결 규칙. `events.jsonl`: 실제 취합 및 검사 결과.

최종 ID는 출처별 원래 문항 번호의 오름차순으로 부여합니다. 상위 `id`, `source_input.id`, 각 항목의 `item_id`를 함께 변경했습니다. 원래 ID와 항목 ID는 `metadata.publication_source` 및 별도 연결표에 보존합니다. 질문·본문·정답은 변경하지 않았습니다. 원문 정답을 변형 문항의 정답으로 가정하지 않습니다.

원천 합본: FinanceReasoning은 `data/generated/20261003-concat-002/dataset.jsonl`, TAT-QA는 `data/generated/20261003-003/dataset.jsonl`입니다. 원천 합본은 유지합니다. 이 작업은 저장 데이터 취합이며 LLM 호출은 없습니다.

원래 단계 자료는 [FinanceReasoning 공통 뷰어](http://127.0.0.1:8893/?run=20261003-concat-002)와 [TAT-QA 공통 뷰어](http://127.0.0.1:8893/?run=20261003-003)에서 연결표의 `source_case_id`로 확인합니다. 이 README는 `src/finarch/documentation/templates/final-dataset.md`에서 생성했습니다.

## EA_INVERSE_REVIEW 전용 합본

1. `EA_INVERSE_REVIEW.jsonl`: `dataset.jsonl`과 같은 최종 ID·순서의 **1354줄**입니다. 한 줄의 `variants`에는 EA_01, EA_02가 순서대로 들어 있어 총 **2708건**을 확인할 수 있습니다. 각 유형의 실제 `question`·`context`·`content_sha256`과 원천 연결 정보를 함께 담습니다.
2. `EA_INVERSE_REVIEW.schema.json`: 합본 구조와 완료·호출 실패·기록 없음의 구분을 정의합니다.
3. `manifest.json`의 `ea_inverse_review`: 출처·유형별 건수, 입력 해시, 실제 원기록과 Q/C의 연결 검사 결과입니다. 취합 이력은 기존 `events.jsonl`에 기록했습니다.

|출처|문항|EA 두 유형|역산 가능 true|역산 불가 false|호출 실패|기록 없음|
|---|---:|---:|---:|---:|---:|---:|
|FinanceReasoning|1071|2142|413|86|1|1642|
|TAT-QA|283|566|485|77|4|0|
|합계|1354|2708|898|163|5|1642|

`review_record`는 저장된 EA_INVERSE_REVIEW 전체 기록입니다. 내부 `inverse_review`의 `inverse_possible`, `missing_quantity`, `reason`, `evidence`, `formula`와 모델·시각·요청 참조를 그대로 보존합니다. `evidence_display_check`도 원래 표시 좌표 검사 기록을 복제하며, 원판정이나 인용 위치를 새로 고치지 않습니다. 원기록의 파일·SHA-256은 `source.review_file`과 `source.review_ref`에 남깁니다.

검토가 완료된 1061건만 `inverse_possible=true/false`를 갖습니다. 호출 실패 5건은 기존 `CALL_FAILED` 기록을 보존하고 `inverse_possible=null`입니다. 기록 없는 1642건은 `availability=MISSING`, `status=NOT_RECORDED`, `review_record=null`, `inverse_possible=null`입니다. 기록 없음은 false가 아닙니다. 누락 항목은 과거 `20260917-002` 제작분의 821문항 × 두 유형이며, 현재 선택된 최종 EA Q/C에 연결되는 저장 기록이 없습니다.

원판정은 남아 있는 Q/C만 본 LLM의 역산 검토입니다. 식의 의미 타당성이나 독립적으로 확정한 정답·근거 gold를 새로 검증한 결과는 아닙니다. 원문 정답이나 대상 모델 응답을 이 합본의 판정에 섞지 않습니다. 새 LLM 호출은 0건입니다.

각 유형의 `source.viewer_url`은 위 공통 dataset viewer의 실제 제작 문항·EA 유형·검증 단계로 연결됩니다. `id-0031`의 EA_01은 [FinanceReasoning 역산 검토](http://127.0.0.1:8893/?run=20261003-concat-002&case=test-0086&variant=06-ea-earlier-input&stage=03-validation), `id-1072`의 EA_01은 [TAT-QA 역산 검토](http://127.0.0.1:8893/?run=20261003-003&case=test-0004&variant=06-ea-earlier-input&stage=03-validation)에서 원래 기록을 확인할 수 있습니다.

이 절은 `src/finarch/documentation/templates/final-ea-inverse-review.md`에서 생성했습니다.
