## EA_INVERSE_REVIEW 전용 합본

1. `EA_INVERSE_REVIEW.jsonl`: `dataset.jsonl`과 같은 최종 ID·순서의 **{cases}줄**입니다. 한 줄의 `variants`에는 EA_01, EA_02가 순서대로 들어 있어 총 **{ea_items}건**을 확인할 수 있습니다. 각 유형의 실제 `question`·`context`·`content_sha256`과 원천 연결 정보를 함께 담습니다.
2. `EA_INVERSE_REVIEW.schema.json`: 합본 구조와 완료·호출 실패·기록 없음의 구분을 정의합니다.
3. `manifest.json`의 `ea_inverse_review`: 출처·유형별 건수, 입력 해시, 실제 원기록과 Q/C의 연결 검사 결과입니다. 취합 이력은 기존 `events.jsonl`에 기록했습니다.

|출처|문항|EA 두 유형|역산 가능 true|역산 불가 false|호출 실패|기록 없음|
|---|---:|---:|---:|---:|---:|---:|
|FinanceReasoning|{finance_cases}|{finance_ea_items}|{finance_true}|{finance_false}|{finance_failed}|{finance_missing}|
|TAT-QA|{tatqa_cases}|{tatqa_ea_items}|{tatqa_true}|{tatqa_false}|{tatqa_failed}|{tatqa_missing}|
|합계|{cases}|{ea_items}|{true_count}|{false_count}|{failed_count}|{missing_count}|

`review_record`는 저장된 EA_INVERSE_REVIEW 전체 기록입니다. 내부 `inverse_review`의 `inverse_possible`, `missing_quantity`, `reason`, `evidence`, `formula`와 모델·시각·요청 참조를 그대로 보존합니다. `evidence_display_check`도 원래 표시 좌표 검사 기록을 복제하며, 원판정이나 인용 위치를 새로 고치지 않습니다. 원기록의 파일·SHA-256은 `source.review_file`과 `source.review_ref`에 남깁니다.

검토가 완료된 {completed_count}건만 `inverse_possible=true/false`를 갖습니다. 호출 실패 {failed_count}건은 기존 `CALL_FAILED` 기록을 보존하고 `inverse_possible=null`입니다. 기록 없는 {missing_count}건은 `availability=MISSING`, `status=NOT_RECORDED`, `review_record=null`, `inverse_possible=null`입니다. 기록 없음은 false가 아닙니다. 누락 항목은 과거 `20260917-002` 제작분의 821문항 × 두 유형이며, 현재 선택된 최종 EA Q/C에 연결되는 저장 기록이 없습니다.

원판정은 남아 있는 Q/C만 본 LLM의 역산 검토입니다. 식의 의미 타당성이나 독립적으로 확정한 정답·근거 gold를 새로 검증한 결과는 아닙니다. 원문 정답이나 대상 모델 응답을 이 합본의 판정에 섞지 않습니다. 새 LLM 호출은 0건입니다.

각 유형의 `source.viewer_url`은 위 공통 dataset viewer의 실제 제작 문항·EA 유형·검증 단계로 연결됩니다. `id-0031`의 EA_01은 [FinanceReasoning 역산 검토](http://127.0.0.1:8893/?run=20261003-concat-002&case=test-0086&variant=06-ea-earlier-input&stage=03-validation), `id-1072`의 EA_01은 [TAT-QA 역산 검토](http://127.0.0.1:8893/?run=20261003-003&case=test-0004&variant=06-ea-earlier-input&stage=03-validation)에서 원래 기록을 확인할 수 있습니다.

이 절은 `src/finarch/documentation/templates/final-ea-inverse-review.md`에서 생성했습니다.
