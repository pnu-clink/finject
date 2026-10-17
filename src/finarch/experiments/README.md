# Target-model Evaluation and Analysis

Use the [Evaluation runbook](01-evaluation/README.md) first, then the [Analysis runbook](02-analysis/README.md). Both use one independent experiment folder under `reports/experiments-run/`. Dataset construction folders under `reports/run/` are a different workflow.

| Stage | Input | Output | Model calls |
| --- | --- | --- | --- |
| E01 Preparation | Generated-format dataset and explicit experiment config | Frozen public/private inputs, prompts, schemas, requests, hashes, and plan | None |
| E02 Request preparation | Selected public Q/C and experiment conditions | Per-model request manifests | None |
| E03 Execution | Frozen request manifests and provider credentials | Saved jobs, raw provider results, usage, errors, and responses | Yes |
| E04 Validation | Saved responses | Format/execution status and numeric comparison records | Python processing |
| A01 Results | Finished Evaluation and verified saved files | Recorded responses and source hashes | None |
| A02 Comparison | A01 rows and private production metadata | Counts, paired outcomes, response assessments, and interpretations | Python counts plus LLM assessment |
| A03 Research | Valid A02 observations and their evidence | Research findings with traceable response references | Yes |
| A04 Quadrant | Completed A03 findings | Grouped findings and linked evidence | LLM grouping plus Python checks |
| A05 Outcomes | Saved response assessments and production metadata | Derived semantic answerability/outcome summaries | Python processing |

E04 format validity or numerical agreement is not a semantic-correctness certificate. Saved analysis judgments and construction/human labels have separate meanings. Missing or failed assessments must remain visible in coverage denominators.

The [small example configuration](../../../config/experiments/reviewer-smoke.toml) selects one supplied final-data family and prepares requests without model calls. Execute Evaluation to collect responses, then follow the Analysis prerequisites and [configuration compatibility](../../../config/README.md).

Entry point: `pipeline.py`. Shared paths, storage, manifests, locks, and settings are under `90-operations/`; prompts/schemas are under `prompts/` and `schemas/`; the [viewer](../../../viewer/experiments/README.md) reads saved artifacts. Each run freezes its definition; do not edit a frozen request/config to change a model or cohort. Prepare a new run for a new Evaluation definition.
