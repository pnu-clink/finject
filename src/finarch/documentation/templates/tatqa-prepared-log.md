# TAT-QA results are delivered; Luna Evaluation starts recording

## This is the job.

By user instructions. `20261003-003`The results of `data/prepared/tatqa/20261003-003`Start the user-selected Luna Native OpenAI Batch Evaluation. Check the actual submission and progress status in the validation and state/job file of the experiment run below.

## Read the order of file roles

1. [Reader's data is delivered](../../data/prepared/tatqa/20261003-003/README.md): 437The original results are preserved, 291Automatic PASS range of the case array, source path, and file role.
2. `validation.json`Source/transmission hash, select ID, public input identification, 4items local return checks, document checks, actual batch-viewer checks and verification limits.
3. `events.jsonl`Data transmission, testing, and connection recording.
4. `prepare.log`The existing: `finarch.experiments.pipeline prepare`The actual output of.
5. [Experiment readme](../../reports/experiments-run/20261003-exp-001-tatqa-luna/README.md)And the experiment. `authorization.json`, `launch-verification.json`, `state.json`, `pipeline-process.json`, `pipeline.log`: synchronous input; transmission range; pipeline and current status.
6. The experiment. `01_evaluation/02_request/plan.json`·`luna-api/manifest.jsonl`, `01_evaluation/03_execution/luna-api/batches/*/job.json`: Expected request; cost; actual condition request and submission Batch ID.

ReadME is a `src/finarch/documentation/templates/tatqa-prepared-log.md`It's generated from.

## Data release range

- The original.7All the transformations are automatic passes. **291Case family**Automatic PASS is different from human approval or meaningful confirmation.
- Original 291+ variable 2,037＝**2,328public inputs**.
- Unguided/Guided × Reasoning OFF(none)/ON(medium)＝**9,312evaluation requests**It's not four repetitions of the same setup.
- The original external classification is 55That's a verification condition, 236The building is unconditional and only private, and this classification doesn't mean the actual use of knowledge of the subject model.
- The Luna model is `gpt-6-luna`Native OpenAI Batch, cache off. The actual cache read/write usage is verified after collection and still 0I'm not sure.
- Cost per request output 1,000From the token-letter number-based input estimate **About $1.3.07**It depends on the actual output tokens, including the inference, and not the bill amount.](https://developers.openai.com/api/docs/models/gpt-6-luna).
- Analysis and new meaning of the call judge are not included in this execution. `run --evaluation-only`And we use Analysis paused.

## Change files and responsibilities

|File|Role|
|---|---|
|`src/finarch/dataset/03-release/export_run_results.py`|`--prepared-output`To the existing results to the new data folder after the hash check. No rewrite.|
|`src/finarch/experiments/00-input/dataset.py`|`results_path` Read the actual copy, source, copy, and current state of production.|
|`src/finarch/experiments/00-input/edit_provenance.py`|Subsequent metadata connections also use the same transmission path|
|`config/experiments/config.toml`|New source_run/results_path/input_path, count=291Private External Use Classification required, Luna experiment name|
|`src/finarch/experiments/checks/test_prepared_results.py`|Byte-reading, identification, failure preservation, copy transfer, source change, other source rejection checks|
|Step by step documentation template|Delivery order, responsibility, actual code flow and new data connections|

## Check the screen.

[Luna's experiment is on the screen](http://127.0.0.1:8894/?run=20261003-exp-001-tatqa-luna&tab=progress) [Luna experiment input](http://127.0.0.1:8894/?run=20261003-exp-001-tatqa-luna&tab=overview) · [Source creation screen](http://127.0.0.1:8893/?run=20261003-003).

The results of the experiment do not create any HTML in the folder. Whether you read the latest data from the API and whether you actually check the browser screen is distinguished from validation.json. Complete submission is different from complete model response collection, format validation, and RQ1 semantic assessment.
