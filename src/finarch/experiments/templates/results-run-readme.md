# {run} Evaluation response reuse and differentiation Analysis

The evaluation source is **{source}**The input, verification request, raw response, format validation file was kept the same byte. **0times**It's not a standalone repeat experiment. **{status}**- Plan response. **{planned}items**.

|Reading order|The data.|Role|
|---|---|---|
|1|[config.json](config.json), [manifest.json](manifest.json)|Reuse source, hash and selected analytical model, effort tag|
|2|[00_input](00_input/README.md)|Public Q/C accuracy and private assessment data|
|3|[Evaluation](01_evaluation/README.md)|Request of source: Folded source: Formatting results.|
|4|[Analysis](02_analysis/README.md)|The results of the study are summarized → Relation comparison → Study interpretation|
|5|[The latest research interpretation](02_analysis/03_research/findings.md)|Observational numbers, actual responses, comparisons, limits, improvements and feedback|
|6|[events.jsonl](events.jsonl), [state.json](state.json)|The progress and persistence of this analysis|

[Experimental Viewer](http://127.0.0.1:8894/?run={run}&tab=analysis)I read the same material in the article. The answering probability trial and past analysis LLM scores are not used as a prerequisite for this analysis.

## Use and start log

`PYTHONPATH=src .venv/bin/python -u -B -m finarch.experiments.pipeline analysis --run reports/experiments-run/{run}`To A01 → A02 → A03Run the step before the start of the `TASK_START`In this, we're going to print the tag: actual model, effort, operation, Python/LLM separation, request, and synchronous limit. `pipeline.log`and `02_analysis/execution.log`Evaluation is a reuse of completed responses and no new grass requests.
