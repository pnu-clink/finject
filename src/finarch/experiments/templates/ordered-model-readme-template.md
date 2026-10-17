# {model}: E04 response-format validation

Transport: `{transport}` · planned requests: {planned} · format-valid responses: {valid}.

1. [Request manifest](../../02_request/{model}/manifest.jsonl): exact prompt, schema, Q/C, precision, and experiment conditions.
2. [Execution records](../../03_execution/{model}/): Batch delivery, raw responses, and per-request exchanges.
3. [Result rows](results.jsonl) · [Format-validation summary](summary.json).
4. [Analysis](../../../02_analysis/README.md): saved-response review and condition comparisons.

Format checks and original-reference numeric comparisons have separate records. Preserve raw responses and every attempt; distinguish not run, failed, and unevaluated states.
