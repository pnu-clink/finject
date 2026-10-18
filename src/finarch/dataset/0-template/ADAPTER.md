# Add a source format through the native adapter interface

For automatic code authoring, follow [Generate a reusable adapter](README.md).
The supplied example uses `data/sample/finqa_10.json` and creates `finqa.py`,
`adapters.finqa()` and `FinqaProvenance`. Reuse that installed runner for more
FinQA data; a different sample size does not require another adapter.

This page is for implementing the same interface manually or with a coding
agent. Read [CONTRACT.md](CONTRACT.md) before changing code. All paths below
are relative to `src/finarch/dataset/`.

| Stage | Template and prompt | Implementation and validation |
| --- | --- | --- |
| 1. Source selection/preprocessing | [template1_source.py](template1_source.py), [prompt1.md](prompt1.md) | Create `00-input/<dataset>.py`; implement `iter_questions(document)` and `preprocess(record, question)`; compare raw coverage and normalized arguments. |
| 2. Common adapter | [template2_adapter.py](template2_adapter.py), [prompt2.md](prompt2.md) | Append `adapters.<dataset>(record, question, source)` in `00-input/adapters.py`; preserve the fixed helper calls and ten return fields. |
| 3. Provenance registration | [template3_schema.py](template3_schema.py), [prompt3.md](prompt3.md) | Add `<Dataset>Provenance` to `schemas/prepared.py` and the existing union; validate the unchanged common input contract. |

The [coding-agent prompt](ADAPTER-PROMPT.md) explains what to inspect and what
may be changed. The automatic authoring tool executes each candidate, compares
its output with the actual raw records, and performs native-loader and existing
Finance/TAT-QA regression checks before installing all three code additions.
Manual implementations must satisfy the same contracts and checks.

## Input decisions

Use the raw question, complete context and **displayed numeric gold answer**.
Preserve decimal precision and original text/table order. Normalize only
explicit literal numeric punctuation using the fixed source helper. For FinQA,
use `qa.answer`; do not replace it with `qa.exe_ans` or execute its program.
Do not infer units, scale, required answer type, financial meaning or a solution
in the adapter. Source selection and punctuation cleanup belong in
`preprocess`; common context locations and numeric reference registration
belong in existing helpers.

The fixed runner computes original file hashes, stable IDs and source pointers,
adds the final sample ID, validates the complete record and writes
`intermediate.json` plus `input.json`. Source evidence and generated README go
to `reports/run/<output-name>/00-input/`. The [output list](README.md#files-created-or-modified)
shows code and data changes separately.

## Convert and continue

Once installed, run `00-input/<dataset>.py` with the raw file paths and a fresh
`--output` directory. Keep the raw files and run evidence. Inspect the actual
question/context, displayed answer and precision against the source, then use
`input.json` with the [Preparation plan and construction commands](../README.md).
Format checks are not a guarantee of semantic correctness or downstream PASS.

The older `adapter_template.py` and `prepare-custom` interface are retained for
existing callers. They are a separate compatibility route and are not the
three-stage interface used by `make_adapter.py` or this FinQA example.
