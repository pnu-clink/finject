# {name} · Human annotation passing the final dataset

`dataset.jsonl`The first line of the 1and 7The final case is the question type, the text, the automatic check, the final passing status. **{cases}entries**The criteria for selection meet the existing manufacturing selection criteria, and the two evaluators will be able to determine the 7It's a case that leaves an APPROVED judgment stored in all types. 7The type of `annotation`All of them. `{"status": "PASS"}`The PASS of the original does not mean that the original has passed the production test, and that it has not done any human annotation.

|Source|Count|Final ID|
|---|---:|---|
|FinanceReasoning|{finance_cases}|id-0001 ~ id-1071|
|TAT-QA|{tatqa_cases}|id-1072 ~ id-1354|

## The file and the reading order.

1. `manifest.json`Selection criteria, source numbers, file hash and source data information.
2. `dataset.jsonl`: source text `original`And the order of the `variants` 7Type. Each item is `annotation` `{"status": "PASS"}`So, what is the value of the `ratings`It doesn't include.
3. [Contact page](../{connection_filename}): `final_id`Look for him. `source_dataset`, `source_run`, `source_case_id`, `source_file`, `source_line_number`I'm going to check it out. `id-0001`The reasoning is that `{first_finance_case}`, `id-1072`The TAT-QA `{first_tatqa_case}`.
4. `dataset.schema.json`: case structure and ID; inline hash; annotation linking rules. `events.jsonl`: actual absorption and testing results.

The final ID is assigned by source to the original case number in the lower case. `id`, `source_input.id`, for each item `item_id`The original ID and the item ID were `metadata.publication_source` The question-text-correct answer has not changed. The original reference answer is not assumed to be the correct answer to the perturbed item.

So, what's the point of this? `data/generated/20261003-concat-002/dataset.jsonl`TAT-QA is the `data/generated/20261003-003/dataset.jsonl`So, the source code is maintained, and this is a data storage operation, and there's no LLM call.

The original step data is from [FinanceReasoning Common Viewer].](http://127.0.0.1:8893/?run=20261003-concat-002)And [TAT-QA common viewer](http://127.0.0.1:8893/?run=20261003-003)From the linking tables `source_case_id`This README is a very simple, very simple, `src/finarch/documentation/templates/final-dataset.md`It's generated from.
