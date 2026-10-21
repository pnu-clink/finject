# Source samples

## FinQA alternative: ten simple passed examples

[finqa_passed_10.json](finqa_passed_10.json) contains ten complete, unchanged
FinQA records selected from the released FInject dataset. The questions ask
for sums, differences or averages. Their saved originals and all seven
variants passed automatic validation on the first round and have released
annotation status `PASS`.

This is a selected demonstration sample. It has no questions in common with
`finqa_10.json`, which remains available separately. Each raw JSON object is
byte-identical to the pinned FinQA test split described below; use `qa.answer`
as the displayed gold answer. No question, table, answer or source field has
been rewritten. A new full construction run has not been performed for this
sample.

| Property | Value |
| --- | --- |
| FinQA test indices, in sample order | `555, 763, 143, 444, 637, 1122, 368, 325, 997, 40` |
| Released FInject family IDs, in sample order | `id-0140, id-0147, id-0451, id-0453, id-0018, id-0209, id-0182, id-0138, id-0023, id-0169` |
| Sample SHA-256 | `aa0d414fad9551d77defa6e38f8e319f3c3dcfbf8155b707ff7f0ec52c83f0bf` |

To convert this file, [reuse the existing FinQA adapter](../../src/finarch/dataset/0-template/README.md#3-reuse-the-adapter-with-new-data)
with `data/sample/finqa_passed_10.json` and a new output directory such as
`data/prepared/finqa_passed_10`. A fresh checkout first needs the adapter
authoring step described below. This selection does not change adapter code.

## FinQA: ten raw questions linked to passing paper examples

Start with [finqa_10.json](finqa_10.json). It contains ten complete original
FinQA records together in one JSON array. Original keys, question text,
paragraphs, tables, displayed answers and numeric spellings are preserved;
each selected JSON object is byte-identical to the pinned source.
These questions correspond to ten families in the paper's
[released dataset](../final/finject-20261007/README.md). Each saved original
and all seven variants have automatic validation status `PASS`; all seven
variants also have released annotation status `PASS`.

| Property | Value |
| --- | --- |
| Source | [FinQA test split](https://github.com/czyssrs/FinQA/blob/0f16e2867befa6840783e58be38c9efb9229d742/dataset/test.json) |
| Revision | `0f16e2867befa6840783e58be38c9efb9229d742` |
| Original split size | 1,147 records |
| Selected zero-based indices, in sample order | `473, 480, 1073, 1046, 74, 679, 854, 1069, 176, 407` |
| Sample SHA-256 | `0527d11e766fbbbf33f3bf15383fbf34898955cc2ca3d8a5f9cd98c615eaef1d` |
| Source SHA-256 | `831dbfb2e785dbc227f895ce3f24046433467aec67b09db2bd6ac7692a8a30dc` |
| Upstream license | [MIT license and copyright notice](finqa-LICENSE.txt) |

The sample deliberately selects previously passing paper examples, in final
family-ID order, with matching displayed numeric answers and precision. It is
a demonstration subset, not an unbiased estimate of construction success.
The smaller `finqa-3.json` remains an unchanged offline regression fixture.

| Sample item | FinQA test index | Original FinQA ID | Paper family ID | Displayed answer |
| --- | ---: | --- | --- | ---: |
| 1 | 473 | `AWK/2018/page_146.pdf-1` | `id-0001` | `20` |
| 2 | 480 | `GS/2017/page_132.pdf-4` | `id-0002` | `-4079` |
| 3 | 1073 | `UNP/2011/page_33.pdf-3` | `id-0003` | `889` |
| 4 | 1046 | `LMT/2014/page_77.pdf-4` | `id-0004` | `-1.9` |
| 5 | 74 | `VNO/2014/page_57.pdf-1` | `id-0005` | `101` |
| 6 | 679 | `GS/2013/page_63.pdf-3` | `id-0006` | `2751` |
| 7 | 854 | `NWS/2019/page_116.pdf-1` | `id-0007` | `28` |
| 8 | 1069 | `ANSS/2012/page_93.pdf-3` | `id-0008` | `76787` |
| 9 | 176 | `ZBH/2015/page_57.pdf-2` | `id-0011` | `-2` |
| 10 | 407 | `ILMN/2008/page_86.pdf-4` | `id-0013` | `1.2` |

The paper received these questions through FinanceReasoning, whose source
records add an answer-format instruction and render FinQA's `table_ori` as
Markdown. Matching checks compare that question prefix, the complete context
rendered from `pre_text` / `table_ori` / `post_text`, and the exact displayed
answer and precision against each released `source_input`. The
[connection table](../final/finject-20261007-connection-table.csv) records the
FinanceReasoning source IDs for the listed paper families.

This sample keeps the untouched FinQA records, including both `table` and
`table_ori`; it does not copy FinanceReasoning's added instructions or the
prepared paper originals. Historical passes therefore do not guarantee an
identical outcome from a new construction run. Check the new run's results.

For this format, `qa.question` is the question; `pre_text`, `table` and
`post_text` supply context in that order; **`qa.answer` is the displayed gold
answer**. `qa.exe_ans` and the source solution program remain in the untouched
raw records but are not used as the pipeline reference or as generated solutions.
For percentage answers in other FinQA records, literal `%` removal preserves
the displayed number, for example `2.9%` becomes
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
