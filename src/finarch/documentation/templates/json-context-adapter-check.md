# JSON text adapter full scan

Running: {run_id} · FinanceReasoning source {source_total}JSON text that's not empty in the middle. {json_targets}And we tested it on a sample.

Transforming through {passed}entries · failed {failed}Calling the LLM 0Chapter: This is an examination of the expression, the free, the original, the position, the input, and not the results of the grassroots verification of correctness or validity of meaning.

|The source.|All|Subject to examination|Pass|Fail|Except for the empty JSON.|
|---|---:|---:|---:|---:|---:|
{counts_table}

JSON is empty. {empty_json_context}Not the JSON object-array text. {non_json_context}That's not the subject of this test. It hasn't changed the current selection policy.

## Adapter automatically applied standard

Depending on the source scheme, the finance or tatqa adapter is selected. The finance adapter applies the tab conversion if the actual context is empty, and the text is configured as it is in the normal text. Both formats can be mixed in the same source, so the source ID alone is not required. The TAT-QA tab structure uses the existing source structure.

The full input generation path is full_finance.prepare → adapters.finance → content.assemble → JSON value; value contrast → prepared.input schema check. The source is left in provider-records.json and the PoT number location is re-registered in the converted context.

## Reading order

1. [summary.json](summary.json): object denominator and result of transformation.
2. [json-context-adapter-check.json](json-context-adapter-check.json): Article by article, translated table, dataset; source position contrast.
3. [prepared-input.json](prepared-input.json)Common input from the new adapter, this is the test data and it didn't overwrite the existing run.
4. [raw-records.json](raw-records.json): Copy of the original record of the subject.
5. [checks.jsonl](checks.jsonl): The actual check log by case.
6. [manifest.json](manifest.json)The results of the analysis of the source are:

## Check it on the screen.

[Common data set viewer](http://127.0.0.1:8893/?run={run_id})You can select the phrase from the left to see the query, the JSON source, the converted table, the segmented source location, the freeform.

## Check the range

- The object tables use the sequence of group names in the source to keep the row order.
- It preserves the numerical literal sign and the numerical, numerical, and null-boolean data pattern.
- So you can tell the empty string, the missing quanta, the missing hash. 0It doesn't change.
- The array covering the existing tab strings unravels the string and connects the source location.
- We compare the converted can to the original token and check the number, the symbol, the coordinate and the whole input scheme.
- The source file is the same as the pre-sharing. The Pre-Preplication-Generation results are not corrected.
- It's not a verification that supports all of the deep overlay JSON that's not in the actual source.

We use this conversion from the new input generated, and to apply it to the existing run, we need to re-verify the PoT number position and graph connection of that input to fit the new text.

## Re-connect verification

The actual full input generated path, common text preservation, synchronized source mixed format can be verified by the following check:

```sh
PYTHONPATH=src .venv/bin/python -m unittest finarch.dataset.checks.test_json_context_adapter
```

This additional integration verification log is stored in adapter-integration-tests.log, and the document connection verification is stored on adapter-intégration-documentation.log.
