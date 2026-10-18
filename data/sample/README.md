# Source samples

## FinQA: ten raw questions

Start with [finqa_10.json](finqa_10.json). It contains ten complete original
FinQA records together in one JSON array. Original keys, question text,
paragraphs, tables, displayed answers and numeric spellings are preserved;
each selected JSON object is byte-identical to the pinned source.

| Property | Value |
| --- | --- |
| Source | [FinQA test split](https://github.com/czyssrs/FinQA/blob/0f16e2867befa6840783e58be38c9efb9229d742/dataset/test.json) |
| Revision | `0f16e2867befa6840783e58be38c9efb9229d742` |
| Original split size | 1,147 records |
| Selected zero-based indices | `3, 5, 6, 7, 9, 10, 11, 12, 14, 15` |
| Sample SHA-256 | `bf6577f604d7c6b07ad5aa4aeae9ee6556a038c4222fefe45ccc425bb1299361` |
| Source SHA-256 | `831dbfb2e785dbc227f895ce3f24046433467aec67b09db2bd6ac7692a8a30dc` |
| Upstream license | [MIT license and copyright notice](finqa-LICENSE.txt) |

The sample contains numeric displayed answers. Empty answers and yes/no
questions are outside this numeric example. Selection follows source order;
records were not chosen by pipeline success. The smaller `finqa-3.json` is
retained as an offline regression fixture.

For this format, `qa.question` is the question; `pre_text`, `table` and
`post_text` supply context in that order; **`qa.answer` is the displayed gold
answer**. `qa.exe_ans` and the source solution program remain in the untouched
raw records but are not used as the pipeline reference or as generated solutions.
Literal `%` removal preserves the displayed number, for example `2.9%` becomes
`2.9` with precision 1; the adapter does not infer scale or solve the question.

### Generate and check the adapter

Complete [installation and credentials](../../README.md#installation-and-credentials),
then run from the repository root:

```sh
.venv/bin/python -B src/finarch/dataset/0-template/make_adapter.py \
  data/sample/finqa_10.json --name finqa --output data/prepared/finqa_10
```

Adapter authoring uses `gpt-6.1-sol` with reasoning effort `low` by default and
makes billable API calls. It creates `00-input/finqa.py`, appends
`adapters.finqa()` and registers `FinqaProvenance` in `schemas/prepared.py`.
The [adapter guide](../../src/finarch/dataset/0-template/README.md#files-created-or-modified)
lists every output category and the exact three code targets.

Inspect `data/prepared/finqa_10/intermediate.json`, then `input.json`. A successful
conversion reports 10 records and zero exclusions. Only these two data files
are written there. Supporting source records, hashes, validation and README
are in `reports/run/finqa_10/00-input/`; code-generation records are in the
adjacent `adapter-generation/`. Keep the original source file at its recorded
path because Preparation verifies it.

Continue with the [Preparation and Generation commands](../../src/finarch/dataset/README.md).
Those stages call models separately. Their outcomes must be checked; ten valid
inputs do not imply ten fully passing generated families. To convert more
files with this same source layout, reuse the generated `00-input/finqa.py`
with the new file paths and a new output directory, without code edits or an LLM.

## Built-in FinanceReasoning and TAT-QA check

The separate `finance-easy.json` and `tatqa-dev.json` retain complete unchanged
records from the pinned sources in [data/raw](../raw/README.md). Their
`manifest.json` and `source-catalog.json` describe those two files only; they
are not required for the FinQA command above.

`finance-easy.json` contains one FinanceReasoning record; `tatqa-dev.json`
contains one document with six questions. This sampler selects one eligible
question from each source. It makes no API calls:

```sh
PYTHONPATH=src .venv/bin/python -B -m finarch.cli prepare \
  --sources data/sample/source-catalog.json \
  --output reports/run/reviewer-sample/00-input \
  --per-source 1 --seed reviewer-sample-v1

PYTHONPATH=src .venv/bin/python -B -m finarch.dataset.schemas.validation \
  --schema 01-preparation.01-source.prepared-input \
  --input reports/run/reviewer-sample/00-input/input.json
```

Use a new output directory when repeating conversion. Expected IDs are
`tatqa-f329027f-e65a-402c-908e-21f0a0d25fe0` and `finance-test-470`. Read the
bundle's README, `preparation-result.json`, `selection-manifest.json`,
`input.json`, `provider-records.json` and selection/exclusion records.
The built-in bundle keeps input and supporting files together under its run
folder. See [built-in conversion](../../src/finarch/dataset/00-input/README.md).
For this route, pass `reports/run/reviewer-sample/00-input/input.json` as
`INPUT_PATH` in the construction guide. Adding a new adapter later changes the
schema fingerprint, so regenerate older input bundles rather than editing
saved manifests.
