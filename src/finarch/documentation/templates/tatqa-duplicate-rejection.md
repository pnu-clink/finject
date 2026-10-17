# TAT-QA · CodeTAT-QA excluded

Currently running TAT-QA `20261003-003`I'm going to financeReasoning. **CodeTAT-QA 288all entries**And we compared it to the original case, regardless of whether or not the codeTAT-QA automatically failed.

|Item|Count|
|---|---:|
|TAT-QA comparison subjects|717|
|CodeTAT-QA comparison subjects|288|
|The original question and the corresponding response|281|
|Rejected TAT-QA case|280|
|The CodeTAT-QA case is unambiguous with question differences|7|
|HTML object for evaluator, before processing → after|512 → 291|

CodeTAT-QA 2That's the TAT-QA. `test-0294` And then we're going to respond to one of them. 281matches 280The paragraphs in the exclusion clause of the Preparation automatic pass is 270items, automatic failure is a 10It's a items. 7It passed through all items types, and the HTML object was a transcript. 221items are excluded.

## Reading order

1. [plan.json](plan.json)CodeTAT-QA source ID → TAT-QA original question UID; document UID; current problem number, both questions and the corresponding row of the actual table.
2. [result.json](result.json)Reject application; conservation of the original hash;7Check to see if the items passing case excludes the output.
3. [events.jsonl](events.jsonl)Reject save power by paragraph:](prior-decisions.json)It's a pre-personally applied judgment.
4. [Custom Viewer](http://127.0.0.1:8893/?run=20261003-003&case=test-0231&stage=07-human-review): TAT-QA `test-0231`Reject and verify the source reason. `test-0001`, `CodeTAT-QA-test-8`It's like a question mark.

## Standards and scope

The hash of the FinanceReasoning source file;`source`We checked the query, and we checked that the TAT-QA source's question UID, query document, UID tag, was the same as the production input. `Answer to/as ...` I've standardized the numerical direction and the quotation marks, the representative million, and I've identified three distinct phrases: `equiption/equipment` The robber, the one already mentioned on the chart. `(in thousands)` Unit, the same weighty question. `the total revenue` expression.

Add to the question matching. **The order of the row names and numbers is at least two rows of the same table.**The comma, the denominator, the percentage, the bracket, the negative, the minus point, and the omitted addition columns were standardized only for comparison purposes. The original, the original text was not modified. The different tables like the questions were sorted out as the corresponding row counts, and they didn't process the equation.

The transcript is unknown. 7It's code-tat-qa. `test-0176`, `test-0421`, `test-0795`, `test-0798`, `test-1124`, `test-1242`, `test-1428`It never automatically rejects changes/rate changes, comparison intervals, cost items, denominator ranges, etc.

Reject is the active preparation parameter of the current run. `07-human-review/03-record-decision/decision.json`It doesn't change the automatic check status to FAIL. 7The items type is dropped together. The past run and source input, CodeTAT-QA, are preserved.

The HTML you downloaded is a pre-existing data, so it doesn't change automatically. **Export the HTML for the evaluator back to the current execution**If you do, 291The items is the target. `results/` The copy is the original. `export_run_results.py`The amount of copy that you keep up to automatic fail record is different from the amount of HTML that you get for evaluation.

## Order to re-create.

```sh
# So we compare the source and the questionnaire, and we make a plan.json.
PYTHONPATH=src .venv/bin/python -B -m finarch.dataset.90-operations.reject_tatqa_duplicates \
  --run reports/run/20261003-003 \
  --codetat-input data/prepared/finance-reasoning/CodeTAT-QA-20261003/input.json \
  --tatqa-input data/prepared/tatqa/full-20260917/input.json \
  --raw-tatqa data/raw/tatqa-dev.json
# When you first apply it, you attach --apply to the command above.
# It doesn't apply if the plan, the source, the existence are changed.
```

This README is a `src/finarch/documentation/templates/tatqa-duplicate-rejection.md`The manufacturing results called for a regenerative LLM; the new quality assessment was not performed.
