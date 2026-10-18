# {dataset}: prepared source input

Prepared **{count}** questions; **{excluded}** questions excluded by explicit
source-category filters. Conversion uses deterministic Python and makes no LLM
calls. Adapter authoring requests, if any, are recorded separately in the
adjacent `adapter-generation/` directory.

Read these files in order:

1. `{intermediate_path}`: question, context, displayed reference answer and precision.
2. `{input_path}`: complete common prepared-input records for the existing pipeline.
3. `selection-log.json`: every declared source-category exclusion.
4. `selection-manifest.json`: original paths/hashes, IDs, counts and input hashes.
5. `provider-records.json`: original records and their locations.
6. `preparation-result.json`: native schema/loader validation status.
7. `input-schema.json`: the exact schema snapshot used for this input.

The `data` output directory contains only `intermediate.json` and `input.json`.
Keep the original raw files at their recorded paths: the native loader verifies
their hashes. No manual source catalog or raw manifest is required.

This is a source input, not a completed generated dataset. Use its `input.json`
with the existing Preparation and Generation commands in
`src/finarch/dataset/README.md`. Source conversion does not launch either stage.
After running Preparation, use the existing Dataset viewer and select that
construction run; conversion alone does not create a viewer construction run.

PASS confirms the declared mapping, numeric/text preservation, schema and input
loader checks. It does not establish the semantic correctness of the raw gold
answer or successful execution of the later LLM stages.

## Continue with the existing pipeline

From the repository root, inspect the plan first (no model calls):

```sh
PYTHONPATH=src .venv/bin/python -B -m finarch.dataset.01-preparation.prepare_schedule \
  --input "{input_path}" --config config/llm.json --plan-only
```

After reviewing the models and call counts, start Preparation (live model calls):

```sh
PYTHONPATH=src .venv/bin/python -B -m finarch.dataset.01-preparation.prepare_schedule \
  --input "{input_path}" --config config/llm.json
```

Preparation creates a new construction run. Use that run's actual printed path
for Generation, not this source-conversion directory. The construction guide
in `src/finarch/dataset/README.md` includes a lookup by input path, the Generation
command and viewer instructions. To convert more raw files of this format,
reuse `src/finarch/dataset/00-input/{dataset}.py`; adapter regeneration is not
needed when only the data changes.
