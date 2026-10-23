# FInject final dataset: finject-20261007

This directory contains the active dataset, its preserved original, schemas, manifests, and saved EA inverse-review annotations. Each JSONL line contains one original and seven variants.

There are **1,354 families**: 1,071 FinanceReasoning (`id-0001`–`id-1071`) and 283 TAT-QA (`id-1072`–`id-1354`). Each family contains one original and seven variants: 9,478 variants and 10,832 total original/variant items. Counts are family/item counts, not Evaluation requests.

Provenance paths are repository-relative; historical construction paths may identify artifacts excluded from this release. Annotators are identified as `Annotator 1` and `Annotator 2`. The manifest records hashes of the distributed files; each item's content hash separately binds its question and context.

## Files and reading order

1. [manifest.json](manifest.json): release format, source counts, construction/human-selection policy, file hashes, and saved provenance.
2. [dataset.jsonl](dataset.jsonl): one family per line, including `source_input`, `original`, `variants`, production-selection metadata, actual Q/C, content hashes, and embedded EA inverse reviews.
3. [dataset.schema.json](dataset.schema.json): record contract. [events.jsonl](events.jsonl): saved release assembly/check events.
4. [Connection table](../finject-20261007-connection-table.csv): links each final ID to the source dataset/run/case/file/line. These are provenance references; excluded historical folders are not prerequisites for reading the released JSONL.
5. [EA_INVERSE_REVIEW.jsonl](EA_INVERSE_REVIEW.jsonl) and [its schema](EA_INVERSE_REVIEW.schema.json): the unchanged source annotations used for the embedded EA reviews described below.

The [field guide](dataset.README.md) describes the embedded `variants[].metadata.inverse_review` structure and omitted fields. The former dataset and schema are preserved as [dataset-original.jsonl](dataset-original.jsonl) and [dataset-original.schema.json](dataset-original.schema.json). [manifest-original.json](manifest-original.json) preserves the previous manifest, including its historical filenames; `manifest.json` identifies the current files.

The seven variants are IC-VALUE before/after, IC-SOURCE Type 1/2, IC-RELATION, and EA-01/02. Use the saved identifiers rather than inferring type from the order of arbitrary files. Final IDs and item IDs were assigned during publication; original IDs remain in the connection table and the preserved original dataset. Do not assume that an original reference answer is the answer to a perturbed question.

## Meaning of approval and missing annotations

The release selection requires the saved construction-selection criteria and confirmed APPROVED decisions from both annotators for all seven variants. Released `annotation` objects expose only `status: PASS`; individual rating details are not distributed in that field. The original's PASS represents construction checks, not an additional human rating of the original. Automated validation, publication selection, and human annotation are distinct.

The active dataset includes all 2,708 EA reviews in `variants[].metadata.inverse_review`. The unchanged source EA inverse file contains 1,354 rows and the same 2,708 EA entries. Their saved counts are:

| Source | EA entries | Inverse possible | Inverse not possible | Call failed | Not recorded |
| --- | ---: | ---: | ---: | ---: | ---: |
| FinanceReasoning | 2,142 | 413 | 86 | 1 | 1,642 |
| TAT-QA | 566 | 485 | 77 | 4 | 0 |
| Total | 2,708 | 898 | 163 | 5 | 1,642 |

Only 1,061 completed reviews have true/false `inverse_possible`. Failed and missing records have null; missing is not false. The source file preserves the saved `review_record` wrappers. The active dataset carries their review contents and complete evidence-display checks in the embedded structure; no reviews were rerun. These are LLM judgments from the remaining Q/C, not independently certified answer/evidence gold and not target-model Evaluation results.

## Use in Evaluation and view examples

The existing generated-data loader accepts this release directly. The [reviewer smoke configuration](../../../config/experiments/reviewer-smoke.toml) selects one family. Follow the [Evaluation guide](../../../src/finarch/experiments/01-evaluation/README.md) to freeze eight inputs and 32 requests without API keys, then the [experiment viewer guide](../../../viewer/experiments/README.md) to inspect the actual original and variants.

The [Dataset viewer](../../../viewer/dataset/README.md) reads construction run artifacts. Saved source paths and `viewer_url` values identify the original provenance; those construction folders are not needed to read this release or prepare Evaluation. Use the experiment-viewer route above to browse the supplied examples.
