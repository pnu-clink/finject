# Preparation stage control

## Entry point

`prepare_schedule.py` reads prepared `input.json` and run configuration, then manages selected cases, rounds, and retries. Run it from the repository root; replace each `PATH_TO_...` placeholder with an actual path.

```sh
PYTHONPATH=src .venv/bin/python -B -m finarch.dataset.01-preparation.prepare_schedule --input PATH_TO_INPUT_JSON --config PATH_TO_RUN_CONFIG --cases-file PATH_TO_CASE_IDS_JSON
```

`--cases-file` accepts an ID list such as `["test-0001", "test-0002"]`. Alternatively use `--cases`; do not combine them. Omitting both selects all input cases. Add `--plan-only` to inspect selection and configuration without executing the pipeline.

Resume interrupted cases in an existing run with:

```sh
PYTHONPATH=src .venv/bin/python -B -m finarch.dataset.01-preparation.prepare_schedule --run PATH_TO_EXISTING_RUN --resume
```

Completed cases are excluded from automatic resumption. Incomplete cases restart at the source stage. The batch path is `prepare_schedule.main` → `run_selected` → `run_case_rounds` → `prepare_run.run` → each stage's `stage.py`. The normal sequence is 01-source → 02-review → 03-calculation → 04-graph → 05-verification → 07-human-review; failures branch to 06-exception-handler. `preparation_pipeline.py` contains the internal `prepare_batch/run_case` path; it is not the current batch CLI entry point.

`--config` supplies execution and profile paths. Hyperparameters supply concurrency, retry limits, and purpose-specific model selection. Check the selected profile's actual `model` and `effort` before execution. Results are saved under `reports/run/<run>/01-preparation`; Generation consumes this run. Creating human-review material is separate from recording a person's decisions.

The scheduler saves effective settings in `01-preparation/runtime-config.json` and passes this file to workers. It includes `run_phase=preparation`, `profiles_path`, and the run's `hyperparameter_path`. Workers read this shared configuration rather than inferring the model-selection phase or version; individual workers do not rewrite it during execution.

See the [Dataset runbook](../README.md) for installation, credentials, and the complete construction sequence. This folder owns the Preparation execution code; saved outputs follow the existing run contract.

| File | Role |
| --- | --- |
| [preparation_pipeline.py](preparation_pipeline.py) | Execute source audit before calculation and stop at human review. |
| [preparation_preflight_retry.py](preparation_preflight_retry.py) | Retry an entirely uncalled batch after native-control verification succeeds. |
| [prepare_queue.py](prepare_queue.py) | Manage scheduler-owned case IDs. Interrupted cases restart at source without feedback reuse. |
| [prepare_run.py](prepare_run.py) | Execute one Preparation case within an explicit stage range. |
| [prepare_schedule.py](prepare_schedule.py) | Save effective runtime configuration, pass it to workers, manage cases/rounds/retries, and collect results and shared records. |
| [repair_failed_preparation.py](repair_failed_preparation.py) | Give previously failed Preparation cases one recorded repair opportunity. |
| [stage_execution.py](stage_execution.py) | Compatibility entry for callers of the former stage dispatcher. |

Substages: [01-source](01-source/README.md) · [02-review](02-review/README.md) · [03-calculation](03-calculation/README.md) · [04-graph](04-graph/README.md) · [05-verification](05-verification/README.md) · [06-exception-handler](06-exception-handler/README.md) · [07-human-review](07-human-review/README.md).
