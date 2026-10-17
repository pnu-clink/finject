# {output_name}

All {input_count}The original text of the case. 7It's a typewriter. `{base_run}`From CodeTAT-QA {replaced_count}cases `{replacement_run}`And as a result, it was replaced. 7Type the full automatic pass clause **{after_all_seven_pass}items**Automatic PASS is separate from human approval.

## Reading the data

1. [results/README.md](results/README.md): Full case, including failure; misdemeanor record.
2. [results/all-seven-pass/README.md](results/all-seven-pass/README.md): 7The final selection of all types passed.
3. Each folder is `00-input.json`and `01~07` It's kind of like a type-by-type JSON. `id`It connects to the.

[Data set screen](http://127.0.0.1:8893/?run={output_name})In fact, the question is:7I see the type modification text. 01~07Generation, each type of 01~05 Step, Python code, graph, raw response, verification basis, human verification. Filters and shortcuts also use the existing functions.

## File and log.

`results/manifest.json.row_source_runs[id]`is the source run of the corresponding row. `source`, `result`, `edit_provenance`, `inverse_review_ref` The path is the source run. `01-preparation/`, `02-generation/`In some cases, the actual step record of the selected source phrase is independently copied, and even if you edit the file, the source run file doesn't change.

[Operating log](../../../log/dataset-concat/{output_name}/README.md)It keeps the replacement records, the source hash, the query expression difference, the scan results.

## How to run

```shell
PYTHONPATH=src .venv/bin/python -B -m finarch.dataset.03-release.concat_results \
  --base-run reports/run/{base_run} \
  --replacement-run reports/run/{replacement_run} \
  --output-run reports/run/{output_name} \
  --source-prefix CodeTAT-QA-
```

The existing output folder doesn't overwrite. There are no LLM calls.
