# Preparation run records

Reading order: `input-selection.json` → `plan.json`, `config.json`, and `schedule-settings.json` → `01-preparation/schedule-state.json` → each case's `run.json` and round folders → `01-preparation/summary.json` and `review-gate.json`.

Model profiles are resolved from the TOML referenced by `config.json` and the purpose-specific hyperparameters. Each saved LLM input records the actual model, prompt, and schema. A new run does not copy model responses from a historical run.

Select this run in the shared viewer to inspect its artifacts. Automated Preparation success is the PASS status in `run.json`; Generation uses a separate command. `timing.json` and logs preserve commands, timestamps, and elapsed time.

## Concurrency records

API work uses the fixed `shared.api.concurrency` limit, currently 200, without CPU-based increases. When fewer cases remain, only those cases run. Actual HTTP requests in the same process share this limit. CLI work retains its CPU-based schedule.

One scheduler owns `schedule.lock` and writes the queue, summary, and review gate. Each worker writes only its own case folder. `queue.json` records current concurrency; `queue.jsonl` records changes over time.

## Resume after interruption

Use `--run <this-run-directory> --resume` to register pending and running case IDs again. Select individual IDs with `--cases` or a JSON array passed to `--cases-file`. Earlier case folders are preserved under `restart-history/NNN-preparation/test-xxxx`; those cases restart at `01-round/01-source`. Other completed cases are retained. Normal feedback-based second and third rounds remain separate from interruption recovery.
