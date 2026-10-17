# fin-arch

This project constructs datasets with value conflicts, source constraints, relational contradictions, and missing required evidence in financial source material. Dataset construction and target-model experiments are separate workflows.

## Dataset Construction

Follow this order: **source dataset → adapter integration → 00-input → 01-preparation → 02-generation**. Run the commands below from the repository root and replace `PATH_TO_...` with actual paths. Use new input and output folders, and pass the run created by stage 01 directly to stage 02. This section describes the common workflow; source-specific commands and dataset settings are collected under [Additional Notes and Specific Cases](#additional-notes-and-specific-cases).

### 1. Prepare a source dataset

Place source files containing the original question (Q), context (C), and answer (A) in [data/raw](data/raw/README.md). Preserve the originals and record each file's path, SHA-256 hash, source URL, version (commit), and adapter name in the source catalog. The source files and catalog are inputs to stage 00. Do not use outputs from previous LLM generation as source data.

### 2. Create and integrate an adapter if needed

Use an existing adapter for a supported source format. For a new format, implement an adapter that converts its Q/C/A records to the common input schema, and connect it through [adapters.py](src/finarch/dataset/00-input/adapters.py). **The current filename is `adapters.py`, not `adapter.py`.** Register the new adapter name in both the catalog and the dispatch logic of the stage 00 entry point.

Adapters construct the context through [content.py](src/finarch/dataset/00-input/content.py). JSON contexts are converted to tabular form by [json_context.py](src/finarch/dataset/00-input/json_context.py). This stage standardizes the input structure without modifying the answers.

### 3. Run 00-input: convert sources to the common input format

Given the source catalog and selection scope, this stage verifies source hashes, selects or excludes records, applies adapters, and validates the input schema. Choose an entry point suited to the source and selection method from the existing [00-input entry point guide](src/finarch/dataset/00-input/README.md).

Use the common [cli.py prepare](src/finarch/cli.py) entry point to sample records from each source. Below, `COUNT_PER_SOURCE` is the number of records to select per source, and `SELECTION_SEED` makes the selection order reproducible.

```shell
# Sample each source in the catalog and create common input records.
PYTHONPATH=src .venv/bin/python -B -m finarch.cli prepare \
  --sources PATH_TO_SOURCE_CATALOG_JSON \
  --output PATH_TO_NEW_INPUT_FOLDER \
  --per-source COUNT_PER_SOURCE \
  --seed SELECTION_SEED
```

To select all records or restrict selection to a particular source, use the arguments of the source-specific entry point. See [Additional Notes and Specific Cases](#additional-notes-and-specific-cases) for the relevant commands and settings.

Read the outputs in this order: the output folder's `README.md` → logs and manifests documenting selection, exclusions, and source provenance → `input.json`, which is the next stage's input. Keep `provider-records.json` in the same folder. **Stage 00 makes no LLM calls.**

### 4. Run 01-preparation: solve the original items and verify calculations and graphs

The entry point is [prepare_schedule.py](src/finarch/dataset/01-preparation/prepare_schedule.py). Pass the `input.json` produced by stage 00.

```shell
# Source review → LLM-generated Python solution → execution and answer comparison → computation graph → verification.
PYTHONPATH=src .venv/bin/python -B -m finarch.dataset.01-preparation.prepare_schedule \
  --input PATH_TO_NEW_INPUT_FOLDER/input.json \
  --config PATH_TO_LLM_CONFIG_JSON
```

Specify the run settings, `profiles_path`, and `hyperparameter_path` in `config.json`. The model and reasoning effort are selected through the profiles and hyperparameters; specify versioned models and profiles when reproducing a particular version. Concurrency and the maximum number of rounds are also supplied through the hyperparameters. The command above processes the full input and does not require `--cases-file`.

A new run is created automatically under `reports/run/YYYYMMDD-NNN`. The `run` value in the final output is the path to pass to the next stage. Artifacts are stored in that run's `01-preparation` folder. Read them in this order: the run's `README.md` → `01-preparation/summary.json` → each item's `run.json` and the source, Python, graph, and verification records for its active round. Select the same run in the shared [dataset viewer](viewer/dataset/README.md). Passing automated verification and receiving a human review decision are distinct outcomes.

### 5. Run 02-generation: generate seven variants within the same run

The entry point is [generate_schedule.py](src/finarch/dataset/02-generation/generate_schedule.py). Pass the same run after stage 01 has completed.

```shell
# Check Preparation eligibility → plan changes → generate text → validate completed text and retry.
PYTHONPATH=src .venv/bin/python -B -m finarch.dataset.02-generation.generate_schedule \
  --run PATH_TO_RUN_FROM_PREPARATION
```

The current entry checks use each Preparation item's `run.json` status and required artifacts. All selected items must have finished processing, and required artifacts must be valid. Only items with an automated PASS proceed to Generation. FAIL/ERROR items are excluded; unfinished processing or invalid artifacts block entry.

Using the same run's `config.json`, hyperparameters, and profiles, this stage generates IC-VALUE before/after, IC-SOURCE Type 1/2, IC-RELATION, and EA-01/02 variants. Failures are routed to `04-exception-handler`; subsequent rounds process only failure types eligible for retry. Results are saved in `02-generation`, with materials for human inspection provided through `05-human-review`. This command does not include Evaluation or Analysis.

Start with the run's `README.md` and `02-generation/README.md`, then select a round, item, and variant type in the shared viewer. Dataset-specific run records are listed under [Additional Notes and Specific Cases](#additional-notes-and-specific-cases).

After all Generation processing finishes, the original Q/C and the actual Q/C for all seven variants are collected automatically in `data/generated/<run-id>/dataset.jsonl`. This record preserves failures and rejections as well. Items meeting the existing selection criteria of passing all seven types with no rejections are marked separately. For the reading order and annotation links, see the combined output folder's template-generated README and the [release guide](docs/01-dataset/03-release/README.md). The shared viewer's **Generated dataset archive** button displays the saved records.

## Running Target-Model Experiments

Follow these steps from the project root. The dataset pipeline handles data generation; the experiments pipeline handles target-model Evaluation and Analysis.

1. Set `evaluation.schedule.dataset.generated_path` in `config/experiments/config.toml` to `data/generated/<construction-run-id>`, and check the model and inference settings.
2. Inspect the settings with `config`, then freeze the experiment inputs and requests with `prepare`. Neither command calls a model. `prepare` prints the new run path.
3. Execute `run --evaluation-only` with that run path. This submits, polls, and collects Native Batch jobs, performs E04 validation, and stops before Analysis.
4. Select the run in the experiment viewer and inspect the E03 cost/execution Python logs or the progress dashboard.
5. Once the analysis metadata is ready and you have decided to run Analysis, freeze the Analysis settings and execute `run` for the same run.

```sh
PYTHONPATH=src .venv/bin/python -u -B -m finarch.experiments.pipeline config --config config/experiments/config.toml
PYTHONPATH=src .venv/bin/python -u -B -m finarch.experiments.pipeline prepare --config config/experiments/config.toml
RUN_PATH=reports/experiments-run/20261003-exp-004-tatqa-luna
PYTHONPATH=src .venv/bin/python -u -B -m finarch.experiments.pipeline run --evaluation-only --run "$RUN_PATH"
```

The `RUN_PATH` above is an actual TAT-QA run example. For a new `prepare` invocation, replace it with the newly printed path. That selection contained 291 original items and 2,037 variants; applying four conditions produced 9,312 requests. Do not treat this as a fixed request count for other datasets.

```sh
tail -f "$RUN_PATH/pipeline.log"
```

`pipeline.log` records the actual Python commands, stages, and Batch processing counts; `events.jsonl` records the detailed history. Do not start a duplicate instance while the same pipeline is running. When resuming an existing experiment, running `prepare` again creates a different experiment folder.

[Experiment source guide](src/finarch/experiments/README.md) · [Stage documentation](docs/02-experiments/README.md) · [Configuration guide](config/experiments/README.md) · [Experiment viewer](http://127.0.0.1:8894/)

## Documentation Reading Order

1. [Overall workflow](docs/README.md)
2. [01 Dataset construction pipeline](docs/01-dataset/README.md): Input → Preparation → Generation → Release
3. Read each stage folder's README for user requirements, detailed steps, actual code, and failure paths.
4. [Stage-specific open issues](docs/01-dataset/99-open-issues.md)
5. [02 Experiment documentation](docs/02-experiments/README.md): Input → Evaluation → Analysis

File and folder numbers follow the actual run order rather than the order of requests. Update descriptions in the documentation for the relevant stage, and keep past executions, settings, and outcomes in their corresponding run records.

## Data, Run Records, and Viewers

- Sources: [data/raw](data/raw/README.md) · Prepared inputs: [data/prepared](data/prepared/README.md)
- Construction run records: [reports/run](reports/run) · Target-model experiment records: [reports/experiments-run](reports/experiments-run)
- Shared construction viewer: [viewer/dataset](viewer/dataset/README.md) · Experiment viewer: [viewer/experiments](viewer/experiments/README.md)
- [Project dashboard](viewer/dashboard/03-project/README.md): sessions, task hierarchy, recent requests, unfinished work, and saved run status. The [two quantitative views](viewer/dashboard/README.md) cover the experiment overview and item-level analysis.
- [Server widget](apps/server-widget/README.md): check status, start or stop the four viewer servers, and open their pages from the menu bar.

The viewers read saved artifacts. Documentation that confirms implementation is distinct from evidence of actual execution or semantic validation. This README does not claim that any particular historical run is currently running.

## Working Guidelines and Earlier Documentation

Follow the user-defined principles in [AGENTS.md](AGENTS.md) and the [agreement record](handoff/understanding-check.md). Earlier versions of the README and docs are kept in the [2026-09-23 archive](archive/20260923-documentation-reorganization/README.md). The newer documents listed above are the current starting points.

For the code layout, read the [source structure and pipeline mapping](docs/01-dataset/90-operations/05-source-layout.md). To launch the viewers, read the [four-server guide](viewer/README.md).

## Additional Notes and Specific Cases

The following notes apply to particular sources and historical runs. Refer to them when using those sources or selection methods with the common workflow above.

### Preparing the full FinanceReasoning input

The entry point is [full_finance.py](src/finarch/dataset/00-input/full_finance.py). The [existing catalog example](data/prepared/finance-reasoning/source-catalog.json) specifies three sources in this order: `finance-easy`, `finance-medium`, and `finance-hard`.

```shell
# Verify FinanceReasoning sources, apply exclusions, and create the full common input.
PYTHONPATH=src .venv/bin/python -B -m finarch.dataset.00-input.full_finance \
  --catalog PATH_TO_FINANCE_CATALOG_JSON \
  --output PATH_TO_NEW_INPUT_FOLDER
```

This program writes the selection log to `selection-log.json` and the manifest to `selection-manifest.json`. For other sources, such as the full original TAT-QA dataset, use the corresponding entry point in the [00-input entry point guide](src/finarch/dataset/00-input/README.md).

### Restricting selection to CodeTAT-QA and preserving existing item IDs

Select CodeTAT-QA from the FinanceReasoning sources above. Add the following argument to the same `full_finance.py` command.

```shell
# Apply the source filter, item ID mapping, and expected count from the hyperparameters.
PYTHONPATH=src .venv/bin/python -B -m finarch.dataset.00-input.full_finance \
  --catalog PATH_TO_FINANCE_CATALOG_JSON \
  --output PATH_TO_NEW_INPUT_FOLDER \
  --hyperparameter PATH_TO_HYPERPARAMETER_JSON
```

Set the hyperparameter `input.source_prefix` to `CodeTAT-QA-`. To preserve existing item IDs, point `input.id_map_path` to the existing `input.json`, and use `input.expected_count` to check the expected count. See the [288-item CodeTAT-QA run record](reports/run/20261003-001-CodeTAT-QA-0917-002/README.md) for the detailed 00 → 01 → 02 commands, logs, settings, and results. Use a new input folder and run for a new execution.

### Historical work records

- [Luna experiment improvement record](reports/run/20260923-experiment-improvement/README.md): prior results, response contracts, limited runs, and comparison reports.
- [Documentation reorganization record](reports/run/20260923-dataset-documentation/README.md): consolidation, original hashes, migration mapping, and viewer checks.
