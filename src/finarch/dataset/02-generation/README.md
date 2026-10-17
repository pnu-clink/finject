# Generation stage control

## Entry point

`generate_schedule.py` reads inputs that passed the Preparation entry gate in an existing run and manages seven perturbation types and retries across rounds. Run it from the repository root and replace `PATH_TO_EXISTING_RUN` with an actual run path.

```sh
PYTHONPATH=src .venv/bin/python -B -m finarch.dataset.02-generation.generate_schedule --run PATH_TO_EXISTING_RUN
```

The default round limit comes from the `generation.schedule.max_rounds` hyperparameter. Add `--resume` to resume interrupted Generation. Restarting completed Generation is rejected. The normal full-run path does not accept `--cases`; case/type selection belongs to the separate path that also uses stage-selection options.

The batch path is `generate_schedule.run` → `generate_run.process` → each stage's `stage.py`. The normal sequence is 01-perturbation → 02-generate-text → 03-validation → 05-human-review; failures branch to 04-exception-handler. Later rounds retry eligible failed types and handle VALUE/SOURCE dependencies.

Execution settings come from the run's `config.json`; model and effort come from selected profile definitions. Hyperparameters control concurrency, round limits, and purpose-specific model selection. Outputs remain in the same run's `02-generation` folder. This construction stage creates review material; it does not supply human decisions or run target-model Evaluation/Analysis.

See the [Dataset runbook](../README.md) for installation, credentials, entry gates, and the complete sequence. This folder owns Generation execution code; saved outputs follow the existing run contract.

| File | Role |
| --- | --- |
| [generate_run.py](generate_run.py) | Generate seven variants from approved inputs with bounded feedback rounds. |
| [generate_schedule.py](generate_schedule.py) | Manage batch cases, types, rounds, retries, and shared records. |
| [stage_execution.py](stage_execution.py) | Compatibility entry for callers of the former stage dispatcher. |

Substages: [01-perturbation](01-perturbation/README.md) · [02-generate-text](02-generate-text/README.md) · [03-validation](03-validation/README.md) · [04-exception-handler](04-exception-handler/README.md) · [05-human-review](05-human-review/README.md).
