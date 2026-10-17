# {run_id}

Response collection: **{status}** · {originals} originals · {variants} variants. Collection and Analysis have separate completion states.

## Reading order

1. [00 Input](00_input/README.md): public question/context/precision and private evaluation references.
2. [01 Evaluation](01_evaluation/README.md): preparation → requests → model solutions → format and numeric checks.
3. [02 Analysis](02_analysis/README.md): result collection → relationship comparisons → research interpretation.

`evaluation` in `config.json` defines target-model execution; `analysis` defines API/Codex Analysis. Execution uses the frozen copy. A separately frozen `02_analysis/config.json`, when present, governs Analysis. Editing the source configuration does not change a running experiment's conditions.

- [Configuration](config.json) · [Request plan](01_evaluation/02_request/plan.json) · [Frozen file hashes](manifest.json)
- [Progress state](state.json) · [Commands and progress](pipeline.log) · [Detailed events](events.jsonl)
- [Response collection report](01_evaluation/04_validation/REPORT.md)

Target-model input is built from public data only. Private data and Analysis results are not sent to the solving model. Valid format does not establish correctness or logical validity. Review findings before adopting changes in subsequent experiments.

`original_external_knowledge` in `private.jsonl` records the external-knowledge classification made during construction of the original. It is not a new assessment of the variant or the solving model. `used=false` means the confirmation criteria were not met; it is not proof of non-use. This metadata is passed only to Analysis A01/A02/A03.

Select this run in the shared experiment viewer; no separate viewer HTML is generated for each result folder.

## Usage and resumption

From the repository root, resume this experiment with:

```sh
RUN_PATH="{run_path}"
PYTHONPATH=src .venv/bin/python -u -B -m finarch.experiments.pipeline run --evaluation-only --run "$RUN_PATH"
```

This command polls/collects the same Batch IDs, performs E04 validation, and stops before Analysis. Do not launch a second coordinator while this run is active. Removing `--evaluation-only` enables the broader coordinator to continue Analysis; its metadata and frozen settings must be ready. A saved pause is not lifted by this command alone.

```sh
tail -f "$RUN_PATH/pipeline.log"
PYTHONPATH=src .venv/bin/python -u -B -m finarch.experiments.pipeline report --run "$RUN_PATH"
```

`report` refreshes the saved collection report without model calls. Provider-processed, locally collected, and format-valid counts are distinct. Inspect E03 commands, costs, and progress in [this run's viewer](http://127.0.0.1:8894/?run={run_id}&tab=costs). Follow the stage READMEs above for details.
