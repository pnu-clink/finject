# {run} · Create a single copy of the data

`dataset.jsonl` **One line at a time. 1and 7Type**It's a data file that contains the original question/context of the original variable, the original correct answer, the precision, the unit source, the automated checking state and the production judgment. `reports/run` It's a research-produced record, and it's not exactly entered into the subject model.

|Item|Count|
|---|---:|
|All cases|{cases}|
|7Type of slot|{variant_slots}|
|The actual Q/C is the stored variation.|{saved_variants}|
|Existing 7Type passing No rejection met the criteria|{production_eligible_cases}|
|The phrase with the production Reject|{production_rejected_cases}|
|The evaluator annotation link|{annotated_items}|
|The evaluator is not checked|{unreviewed_items}|

## Reading order

1. `manifest.json`: Full merger policy; existence selection policy; source hash; annotation status.
2. `dataset.jsonl`: `source_input`The silver is prepared source, `original`The final preparation input, `variants`The order of the 7Types. Each includes a real Q/C and a content map. The microbial type is Q/C is null and NOT_RUN, and it doesn't make the correct answer arbitrary. It doesn't assume that the correct answer of the variation is the same as the original reference answer.
3. `dataset.schema.json`: case, type, and case structure. `events.jsonl`: Accomplish visual; open; call LLM 0 The record.
4. [Custom Viewer](http://127.0.0.1:8893/?run={run})The execution of the **Generated dataset archive** The source of the file in the save button;7I check the type and the status and download it.

## Failed. Reject. Mis-examination

The whole set keeps to fail, evaluate, and reject. `production_selection.eligible`Only the existing **Preparation PASS + 7All types are PASS + No explicit rejection**It's a good example of how to use the existing evaluator HTML and `results/`The rules of selection do not change.

`automatic_validation`It's an automated test. `production_review`It's a production decision. `annotation.status=UNREVIEWED`And empty ratings are not connected to the evaluator's judgement, and they're not Accept. Automatic PASS doesn't mean accurate answer or human approval.

The variations reflected in the final human annotation pass list are `annotation={{"ratings": [], "status": "PASS"}}`This format only provides a passing state and does not contain the evaluator's detailed results. The annotation of the articles and articles outside that list does not change. The default annotation for the automatic addition continues to be UNREVIEWED.

## The annotation connects

`annotation.schema.json`The format is based on the rating structure of the `finarch-generated-annotations-v1`The JSON is the `ratings` I'll make a list. `item_id`, `content_sha256`, `reviewer`, `decision`(APPROVED/REJECTED/PENDING), `confirmed`, `comment`, `updated_at`The ID and Q/C hashes must match. They store the assumptions of multiple evaluators and don't arbitrarily make the final judgments.

```shell
# I'm reading the current output and I'm adding it.
PYTHONPATH=src .venv/bin/python -B -m finarch.dataset.03-release.publication.consolidate \
  --run reports/run/{run}
# When you connect an annotation, --annotations PATH_TO_RATINGS_JSON and
# --output PATH_TO_NEW_ARCHIVE_DIRECTORY is added. The existing copy is not overwritten.
```

The entire execution of the Generation Summit automatically adapts after saving all the parameters, audit data and reports. `src/finarch/documentation/templates/generated-dataset.md`It's generated from.
