# {run_id}

Grass collection: **{status}** · The original {originals}The automatic inspection passing transformation {variants}Finished is the end of grass collection and the end of content analysis and research review.

`CACHE_POLICY_BLOCKED`This means that the cache blocking function is not verified and stopped before the call. Don't read the plan dry as the actual response number. `REPORT.md`And by model. `cache-preflight.json`The latest execution policy prohibits the reuse of response read-write and other executions, and the original records of previous executions are kept as they were.

`CACHE-AUDIT.md`If you have, you'll first read the actual cache usage of the previous execution, the input-prompt identification, the blocking cause and the default alternatives.

## Reading order

1. `REPORT.md`: Model-by-model execution situation, result interpretation, use and cost.
2. `plan.json`, `config.json`: Call number and set fixed.
3. By model. `01-requests/manifest.jsonl`Examples of the following: case connection; test conditions; full input; prompt; schema; execution criteria. Selection order; rules; external private sources; verification `events.jsonl` `INPUT_SELECTION`I'm going to write it down.
4. By model. `03-results/summary.json`, `results.jsonl`: Conditional denominator · Answering · Exam results.
5. By model. `Calls/<Help>/<type>/<Helping>-P0-R-off.json`It reads the actual request, response, query, usage volume as one file. `I'm going to try to get a copy of this.`It preserves the original record of the case.
6. `events.jsonl`, `state.json`Re-opened: Check the progress record.
7. `layout/README.md`It's the result of a hash and verification of the path correspondence of the execution that moved the previous folder.
8. The Codex model folder is `resources.jsonl`, `resources-latest.json`: 2The CPU memory of the short-range system, the simultaneous processing limit, the number of requests in progress, is generated only when the Codex is running.
9. Native Batch running `<model>/02-batches`It's the transfer file, the batch ID, the manufacturer's output, the actual usage.
10. Running through the content review `02_analysis/01_response_review/README.md` → `02_analysis/02_comparison/summary.json`It's a comparison of input and response, including LLM judgments, reviews, and reviews. 02 I read it in Analysis.

The format was running. `00-definition/response.schema.json`And check the model-by-model manifest. `public.jsonl`There's a free Q/C and a free `answer_format.decimal_places`And we're going to save them together and send them to the LLM and read them publicly. `private.jsonl`It's an evaluation tool that uses the correct answer and the generated basis. It doesn't replenish digits or other information from private when requested. `input-selection.json`The number of cases is not the requested row count, but the sum of the individual item_id of the manifest. `manifest.json`If there's no digit in the public of the previous run, you have to modify the original and prepare new entries in the dataset, so past responses and syntax requests read as then defined. `00-definition`The prompt schema readme template is saved as a copy at runtime.

And we're running it as a Markdown document that doesn't show up in the experiment. `viewer/experiments`It reads the actual storage results of this execution, and doesn't generate any HTML for each resulting folder. It stores the raw response, usage, and scan records in JSON/JSONL.

Re-opened: `PYTHONPATH=src .venv/bin/python -m finarch.experiments.01-evaluation.pipeline run --run "{run_path}"`

Only when you reopen after the end of the restoration. `--resume-limits`The semantic assessment only applies to responses with actual content review files, and does not interpret the default value of the analytical LLM as gold or human approval.

3The re-creation, the analysis, the debate, the renewal of the experimental development of the car. `finarch.experiments.90-operations.three_rounds tick`This is responsible for the use of common input judgments between variables and the actual improvement decisions. `ANALYSIS.md`·`analysis/README.md`·`CASE-STUDIES.md`The file is only in the run that it was created.

The current V6 is a non-zero-sum `answer`and `answer_meta.negative`·`answer_meta.scale`It checks for consistency and uses the same JSON structure as P0/P1. The absence of a numerical answer distinguishes it from a Ubo validity judgment.
