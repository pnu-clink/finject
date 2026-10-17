# Reviewer viewers

The two pipeline viewers read saved files. Starting a server does not create a dataset, run a target model, or execute Analysis. Complete the [installation](../README.md#installation-and-credentials) first. No API key is needed just to read saved artifacts.

| Workflow | Guide | Default address | Saved input |
| --- | --- | --- | --- |
| Construction: Preparation / Generation | [Dataset viewer](dataset/README.md) | http://127.0.0.1:8893/?lang=en | `reports/run/<construction-run-id>/` and its linked generated archive |
| Target-model Evaluation / Analysis | [Experiment viewer](experiments/README.md) | http://127.0.0.1:8894/?lang=en | `reports/experiments-run/<experiment-run-id>/` |

Run each server in a separate terminal from the repository root:

```sh
PYTHONPATH=src .venv/bin/python -B -m finarch.dataset.viewer.server --open
PYTHONPATH=src .venv/bin/python -B -m finarch.experiments.viewer.server --open
```

The second command also requires Node.js on PATH. Open the English URLs in the table or use the English display control. Selecting English changes interface labels; raw responses and source data retain their saved text.

On macOS the corresponding `start.command` files can be double-clicked after setup. The optional [distributed widget](../apps/README.md) starts/stops viewers and opens their pages. Its source is under `apps/server-widget/`; the packaged app is under `apps/`. The widget does not replace Python/Node setup or supply credentials. The other dashboard/research servers are optional authoring views and are not prerequisites for these two pipelines.

Stop a terminal-launched viewer with Ctrl+C. If the default port belongs to another checkout, use `--port 18893` / `--port 18894` and open that address; do not mistake another project's running server for this release. Use a regular local checkout path rather than a symlink or temporary `/var` path.

## What a fresh checkout can show

After the offline [Evaluation prepare](../src/finarch/experiments/01-evaluation/README.md), the experiment viewer displays the actual final-data original and seven variants, their frozen requests, and **Not run** response states. Use this route to inspect released examples without an API key.

The Dataset viewer shows **No run records in reports/run yet** until a construction run exists. To inspect supplied final-data examples, use the Evaluation preparation and experiment-viewer route above.
