# FinanceReasoning Full Preparation Run before the

The source. {total}The first one is empty. {empty_context}Except that → boolean right answer {boolean_answer}Except for the Q.C. Full overdub. {duplicate_qc}Except for that. **{selected}entries**The blank text contains the blank and JSON blank array, the client object, the string, the null.
This result is input preparation and local code testing, and we didn't call the new POT-verification API, and we never reused the old LLM response.

|The source.|All|No title|boolean|Q.C. Reproduction|Final|
|---|---:|---:|---:|---:|---:|
{count_rows}

## Remove the overlay

So I compared the question to the article in the exact sequence, and if the question is different in the same article, I kept the one that came first in the easy → medium → hard and the original sequence, so the bottom six pairs are the same. **The original ID.**And the run ID corresponds to selection-manifest.json.

|The original.|Except for the original.|Reference answer|
|---|---|---|
{duplicate_rows}

The source file was saved, except for the new executable input.json.

## Python language research

The object is final. {selected}entries **The original python_solution**I read it as AST and the original program didn't run, and I didn't measure the failure rate of the new POT.

|The graph is a comparison of the graph.|Number of cases|
|---|---:|
{syntax_rows}

Except for the type-intercepted transcript. **{union}entries**So the original root and the table indexing, which are covered by a single function, are only recorded as a single structural statistic. `a if condition else b`The current graph supports the new POT so you can write it in different expressions so you don't automatically exclude these things.

## Schedule and check for collisions

- API: shared.api.concurrency=200Preparation/Generation using only API is not up to the CPU regardless of the 200It's fixed to the case, and if you have fewer objects, you run the number.
- The overlay generation of the same process and the requests for token counters also have HTTP requests. 200It's not a limitation that combines multiple independent process servers.
- The same run only has one scheduler called schedule.lock, which unlocks the dead process's OS lock.
- The output per case is stored in the path of each worker's assignment. Queue; summary; review-gate is recorded by the scheduler. The common log maintains the existing lock and sequence processing.
- Local tests. 200I'm a items worker. 250You can handle the individual files, the common logs. 250So, I've checked the statistical records of the state thread. 429It's not a network stability test.

## Reopened after the break.

`01-preparation/schedule-state.json`The default object is the unfinished ID. `--cases` Or `--cases-file`You can also set the ID to R.

The previous folder of the reopened object is `restart-history/NNN-preparation/test-xxxx`And then you move it to the same case number. 01-round / 01-source again. Do not write the previous code response feedback. Keep the other cases that are completed. 2·3The error feedback repeat of the car is the traditional way.

```bash
# This input is the order used for the AST investigation
PYTHONPATH=src .venv/bin/python -m finarch.dataset.00-input.full_finance --catalog data/prepared/finance-reasoning/source-catalog.json --output '{input_directory}'

# Verify the run plan without API call
PYTHONPATH=src .venv/bin/python -m finarch.dataset.01-preparation.prepare_schedule --input '{input_directory}/input.json' --plan-only

# Then use the actual run time (not running in this operation)
PYTHONPATH=src .venv/bin/python -m finarch.dataset.01-preparation.prepare_schedule --input '{input_directory}/input.json'

# Re-register the unfinished case ID of the interrupted run
PYTHONPATH=src .venv/bin/python -m finarch.dataset.01-preparation.prepare_schedule --run reports/run/RUN_ID --resume

# Just a few cases from the beginning.
PYTHONPATH=src .venv/bin/python -m finarch.dataset.01-preparation.prepare_schedule --run reports/run/RUN_ID --resume --cases test-0002 test-0010
```

## The file and the reading order.

Input folder: `{input_directory}`

1. This README: Summary of the transformation, multiplication, and transformation methods.
2. finance-preflight.json: The common viewer reads the results of the survey and the basis.
3. Enter the folder selection-log.json: all excluded ID; EU duplicate representative ID.
4. Enter the folder code-syntax-audit.json: Categories of the phrase ID and sub-submission call name.
5. Checks.log: This is the local check run.

From a common viewer. `{run_id}`You can select the same content and then you can open the phrase ID by phrase.
