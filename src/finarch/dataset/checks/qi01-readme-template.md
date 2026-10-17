# QI01 Restricted restoration testing · Local results

This is a local test that reads the final text and static fixture that's stored. 0It's a circle. 20260916-001 The results and the data don't change.

- Running ID: `{run_id}`
- Local inspection: {tests_run}, failed {failures}, errors {errors}items
- In order of reading: `summary.json` → `tests.txt` → The phrase folder `observation.json` → `03-validation/05-recovery-screen.json` → `run.json`
- Common Viewer: [Open this run](http://127.0.0.1:8893/?run={run_id})You select the execution and the case, and then you read the recovery, usage, and judgment range of the actual JSON in the result file.
- `test-0026-06`Delete value: 428501The average. 425855And then we'll restore the remaining tables.
- `test-0074-06`, `test-0074-07`Each of the three assets weighs 40%, 30%I'm going to restore it.
- `viewer-check.json`: This is a record of verifying that you've read three results from the actual data reading function of the common viewer.

The policy is basically off. `ea_recovery_policy.enabled=true`Only when the plan preview, the latest course check, the block judgment work. `full_EA_verdict=NOT_EVALUATED`RECOVERABLE is the actual counterpart to the registration range, and UNKNOWN is not a valid judgment of EA's establishment or default.

The first version only supports two registered grammar: a continuous Current Federal/State line and a blank label string. 2The annual tax table, a portfolio allocation phrase stating that the entire portfolio is three assets. The blank, corporate name, reporting, asset name variations within the support structure are checked. Any synonyms, common labels, other asset sub-level conversions, direct re-engineering, and general solution are not supported and are UNKNOWN. The actual first version returns RECOVERABLE or UNKNONOWN and does not issue NO_WITNESS_IN_SCOPE on a pass basis.

Re-election of the subject;06/07 The candidate's joint reservation, resuming budget, and two-world configuration are reserved. The handler has only the closing quarter that does not pass these two blocking reasons to the LLM.

I misidentified the reference type of the test input during the initial test. 1entries `integer`It's not a number conversion rule error. 46of 44The items passes, the preparation `test_graph_mismatch_does_not_publish_accepted_graph`(Question fixture misses) and `test_pot_request_preserves_metadata_but_excludes_gold`(answer_metadata expectation difference) left it out of range.1And we're only running a direct-linked return check, which doesn't mean that the failure is solved.

Reproduction order: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m finarch.dataset.checks.run_qi01_checks --output reports/run/new-QI01- Thank you very much.`The result is that you refuse to overwrite the folder.
