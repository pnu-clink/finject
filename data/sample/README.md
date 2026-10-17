# Source sample

This folder contains two complete, unchanged records from the pinned sources already included in [data/raw](../raw/README.md). It is a small installation and adapter check, not the paper's evaluation cohort. It contains no generated model responses.

Read `manifest.json` first for original file hashes, record indices, selected question IDs, and subset hashes. Then read `source-catalog.json` for the adapter, source URL, commit, and local subset path. `finance-easy.json` contains one FinanceReasoning record; `tatqa-dev.json` contains one TAT-QA document with six questions. The input builder selects one eligible question per source, not every question in the TAT-QA document.

## Prepare the sample

Complete the [installation](../../README.md#installation-and-credentials), then run from the repository root:

```sh
PYTHONPATH=src .venv/bin/python -B -m finarch.cli prepare \
  --sources data/sample/source-catalog.json \
  --output data/prepared/reviewer-sample \
  --per-source 1 --seed reviewer-sample-v1

PYTHONPATH=src .venv/bin/python -B -m finarch.dataset.schemas.validation \
  --schema 01-preparation.01-source.prepared-input \
  --input data/prepared/reviewer-sample/input.json
```

Use a new output directory for another attempt. The builder refuses to overwrite an existing directory. No API key or model call is needed.

Expected result: two prepared inputs and `model_calls: 0`. With this catalog and seed, `test-0001` is `tatqa-f329027f-e65a-402c-908e-21f0a0d25fe0`; `test-0002` is `finance-test-470`. TAT-QA questions excluded as non-arithmetic or duplicate context remain recorded in the selection metadata.

## Output files and next step

Read the files in this order:

1. `preparation-start.json` and `preparation-result.json`: attempt status, counts, exclusions, and errors.
2. `selection-manifest.json`: source hashes, selection, schema, and input integrity.
3. `input.json`: common records for Preparation, including Q/C, numeric reference, source locations, and provenance.
4. `provider-records.json`: preserved raw records used to verify source integrity. Keep it next to `input.json`; it is not the target-model prompt.

Keep all five files together. Continue only when `preparation-result.json` reports PASS; a failed attempt is not a complete Preparation input.

Continue with the [Dataset runbook](../../src/finarch/dataset/README.md), starting with its offline Preparation plan. This sample is source material for construction. To inspect already constructed examples or freeze target-model requests, use the separately supplied [final dataset](../final/README.md) and [Evaluation runbook](../../src/finarch/experiments/01-evaluation/README.md).
