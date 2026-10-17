# Experiment configuration entry points

Read the shared [configuration and credential guide](../README.md), then the [Evaluation](../../src/finarch/experiments/01-evaluation/README.md) and [Analysis](../../src/finarch/experiments/02-analysis/README.md) runbooks.

- `reviewer-smoke.toml`: a small example using one final-data family, one Evaluation model, four prompt/reasoning conditions, and concurrency one; prepares 32 requests. See the shared guide for Analysis compatibility.
- `config.toml`: expects `data/generated/20261003-003`. Set its dataset path/count when using your own generated dataset.
- Other JSON/TOML files: provider-specific settings. Set model access, credentials, dataset paths, output budgets, and concurrency before preparing a run.

Use an explicit config in `pipeline config` and `pipeline prepare`. Preparation freezes resolved settings; later edits to this directory do not modify a frozen run. `configure-analysis` freezes the separately reviewed Analysis definition into that run. Use a new run when changing the Evaluation model or cohort.
