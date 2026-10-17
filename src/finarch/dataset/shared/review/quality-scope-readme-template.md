# QI05 Audit and certification scope report

The original run `{source_run}`The frozen Q/C and the current generated audit raw response requests are new reports that read the timely model profile decision/history. 0calls.

## The results and the reading order.

- All {records}entries / originals {original_cases}I'm going to have to go. {unique_qc}That one.
- Frozen Q/C match {qc_matches_frozen}I'm going to create a PASS. {generation_pass}All three audit verification axes are passing. {three_audit_axes_pass}That one.
- `BULK_AT_USER_DIRECTION` {bulk_at_user_direction}That's it, independent review of the case. `NOT_REVIEWED` {independent_not_reviewed}That one.
- EA's full judgment `NOT_EVALUATED` {ea_full_not_evaluated}entries. QI01 The real half-life. {qi01_counterexamples_linked}The text matched the observation of the building and then connected separately.

1. `summary.json`: the denominator and the denominator.
2. `quality_scope.json`: Thank you for each case 3I check the axis, the source of the win, and the independent review. `skip_reasons`If you're going. `NOT_EVALUATED`.
3. `manifest.json`: The path of the actual read file/SHA256And check the unchanging after you finish reading.
4. [sidecar-schema.json](sidecar-schema.json): new sidecar dedicated JSON Schema`src/finarch/dataset/schemas/quality_scope.py`It's not an LLM response schema, and it doesn't change the existing LLM schemes and exit registry.
5. `events.jsonl`Start, complete, fail log. `checks.txt`·`checks.json`·`viewer-check.json`If this is the local verification,

[Open this run in the public viewer](http://127.0.0.1:8893/?run={run_id}) The report reads only the JSON stored and reflects the latest file changes. The original creation/editing/authentication record is opened with a hash-verified read-only link. QI01 It also provides a link to the results, and the existing QI01 The folder keeps it. It doesn't create any resulting HTML.

## Interpretation restrictions

The three verification axes are `planned_change`(planned change) `unintended_change`(Unnecessary changes) `readability`(Gasps) 3It's not a mistake, it's three judgments made in each case. `FINAL_TEXT_ONLY` PASS is not a complete meaningful, proof-of-EA, independent person review, nor does the authorization of user instructions transform into an independent case review. It does not assume that only the reviewer=user of past history had an actual independent meaningful review.

The report. `NOT_REVIEWED`So if you're going to get an actual independent review, you're gonna have to link it to the new version. `UNKNOWN`That's the old audit and approval records and the new QI0.1 The half-circle remains in the same state.

Reproduction: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m finarch.dataset.shared.review.quality_scope --source reports/run/{source_run} --output reports/run/new quality-run --qi01 reports/run/20260916-qi01-v1`If you refuse to overwrite the existing output path and change the input, `SNAPSHOT_CHANGED`He's a record failure.
