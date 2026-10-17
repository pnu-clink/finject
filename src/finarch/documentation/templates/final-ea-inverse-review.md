## I'm going to give you a copy of the EA_INVERSE_REVIEW.

1. `EA_INVERSE_REVIEW.jsonl`: `dataset.jsonl`The final ID sequence is like **{cases}lines**So, this is a line. `variants`In the case of EA_01, EA_02Go in the order. **{ea_items}entries**You can check for each type of real `question`·`context`·`content_sha256`And it's a link to the source.
2. `EA_INVERSE_REVIEW.schema.json`It defines the composition of the syntax structure and the completion, the output, the failure, the no-record.
3. `manifest.json` `ea_inverse_review`Sources: type-specific drainage, input time, actual source records and Q/C connectivity tests. `events.jsonl`I wrote it down.

|Source|Case|EA two types|This is true.|Reverse is not possible false|Failed call|No record|
|---|---:|---:|---:|---:|---:|---:|
|FinanceReasoning|{finance_cases}|{finance_ea_items}|{finance_true}|{finance_false}|{finance_failed}|{finance_missing}|
|TAT-QA|{tatqa_cases}|{tatqa_ea_items}|{tatqa_true}|{tatqa_false}|{tatqa_failed}|{tatqa_missing}|
|Total|{cases}|{ea_items}|{true_count}|{false_count}|{failed_count}|{missing_count}|

`review_record`The entire record is stored in EA_INVERSE_REVIEW. `inverse_review` `inverse_possible`, `missing_quantity`, `reason`, `evidence`, `formula`And it preserves the model, the view, the request. `evidence_display_check`It also copies the original display coordinate check record, and it doesn't repair the original or the citation location.256 `source.review_file`and `source.review_ref`So let's just leave it there.

The review is complete. {completed_count}entries only `inverse_possible=true/false`The call failed. {failed_count}entries use the existing `CALL_FAILED` We keep records. `inverse_possible=null`It's not recorded. {missing_count}entries `availability=MISSING`, `status=NOT_RECORDED`, `review_record=null`, `inverse_possible=null`So, the missing item is not false. `20260917-002` of the constructed data 821It's a case × two, and there's no storage record that connects to the final EA Q/C that's currently selected.

The original review is a reverse review of the remaining Q/C-based LLM. It's not the result of a new verification of the validity of the meaning of the statement or an independently verified correct answer. 0entries.

Each type of `source.viewer_url`The above common dataset viewer is linked to the actual creation clause, type EA, verification step. `id-0031`The EA_01[FinanceReasoning reversal review](http://127.0.0.1:8893/?run=20261003-concat-002&case=test-0086&variant=06-ea-earlier-input&stage=03-validation), `id-1072`The EA_01The [TAT-QA reverse of the](http://127.0.0.1:8893/?run=20261003-003&case=test-0004&variant=06-ea-earlier-input&stage=03-validation)You can check the original records.

This section is... `src/finarch/documentation/templates/final-ea-inverse-review.md`It's generated from.
