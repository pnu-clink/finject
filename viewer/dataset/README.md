# Dataset viewer: construction evidence

This viewer covers Dataset Preparation and Generation. It includes construction references and review metadata; do not use its full payload as the target-model prompt. Evaluation and Analysis belong to the separate [experiment viewer](../experiments/README.md).

## Start and select a run

From the repository root, after [installation](../../README.md#installation-and-credentials):

```sh
PYTHONPATH=src .venv/bin/python -B -m finarch.dataset.viewer.server --open
```

Open http://127.0.0.1:8893/?lang=en and select English if needed. On macOS, `viewer/dataset/start.command` launches the same server. No API key is needed to inspect saved data.

Choose **Select a run**, then the round and case matching the path printed by [Preparation](../../src/finarch/dataset/README.md). Clear search/filters if an existing case is hidden; **Include Preparation failures** keeps failed construction inputs visible. Run IDs, case counts, and variant-record counts have different meanings.

If no construction run exists, the viewer shows **No run records in reports/run yet.** It lists runs under `reports/run/`, rather than arbitrary JSON files. Use the [Evaluation preparation/viewer route](../experiments/README.md) to inspect supplied final Q/C without model calls.

## Read Preparation and Generation in order

1. Open the run guide/summary and verify the selected run/round/case.
2. Inspect Preparation's source question/context, reference, evidence review, generated Python and execution, computation graph, verification, and actual prompts/raw responses. A numeric/reference mismatch, an API error, and a semantic-review failure are different outcomes.
3. After Generation exists, select one of its seven types. Compare the original with the actual variant Q/C, perturbation plan, text-generation records, validation, exceptions, and later rounds. An empty or failed artifact must not be read as PASS.
4. Read human review decisions separately from automated validation. Review/recheck controls can write decisions or schedule work; opening the viewer alone does not perform a human approval or a new model call. Avoid those controls when only inspecting.
5. After full Generation/consolidation, **Generated dataset archive** displays and downloads `data/generated/<run-id>/dataset.jsonl` for the selected construction run. It is not currently a general `data/final` file picker.

The server and data-loading logic are in `src/finarch/dataset/viewer/`; this directory contains browser assets. Saved evidence remains under `reports/run/`, and archives remain under `data/generated/`. Stop the server with Ctrl+C; use `--port` for another port. The [widget guide](../../apps/README.md) describes the optional macOS launcher.
