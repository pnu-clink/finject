# Converted source inputs

Converted **{count} questions**; explicitly excluded **{excluded} records**.
This conversion uses Python only. It does not solve questions, infer answer
units, call a model, or establish semantic correctness.

Read these files in order:

1. `preparation-result.json`: PASS/FAIL and zero model calls for the converter.
2. `intermediate.json`: the adapter's five fields: `q`, `c`, `a`,
   `a_precision`, `a_type`. Compare actual questions, contexts and answer tokens
   with the source records before starting construction.
3. `provider-records.json`: original record snapshots and `origins` for every
   contributing file/record, linked to intermediate items by `intermediate_index`.
   Exact original numeric spellings remain in the hash-verified raw files.
4. `selection-log.json`: all explicit exclusions and the selection policy.
5. `input.json`: the common Preparation input, with IDs, reference fields,
   context locations and source provenance added automatically.
6. `selection-manifest.json`: original file paths/hashes, adapter hash, schema,
   item IDs, and hashes for the three data files.

`preparation-start.json` records the attempted conversion even when it fails.
Keep this complete directory and the unchanged source files together. Use a new
output directory for another conversion; existing outputs are never overwritten.

The intermediate has no scale field. For compatibility with the existing PoT
request, the builder writes `answer_metadata.scale: null` in `input.json`.
It does not infer a scale or consume a source-specific scale annotation. Preserve
all explicitly supplied units, captions and footnotes in the rendered context.
The sign is derived from the answer, never requested from the adapter.

Context locations refer to the normalized `intermediate.json` context, not to
invented raw field names. Raw locations are recorded separately in `origins`.
The generic builder does not reconstruct a custom source's table-cell mappings.

From the repository root, use the Dataset construction runbook with this
directory's `input.json`. First run `prepare_schedule --plan-only`; this verifies
the bundle without model calls. Live Preparation then reviews Q/C and may revise
their wording before PoT generation. Its reviewer receives the reference answer;
the PoT author receives type/precision but not the reference answer itself.

Source conversion alone does not create a Dataset viewer run. The construction
viewer reads subsequent runs under `reports/run/`. For custom source layouts,
inspect `origins` alongside `intermediate.json`; built-in raw-comparison panels
were written for FinanceReasoning and TAT-QA. No variants or target-model results
are produced by this conversion.
