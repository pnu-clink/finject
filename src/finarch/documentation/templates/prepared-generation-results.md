# {run_name} • Production results for experimental delivery

## Purpose and condition

Production run `{source_run}` `results/` `{output}`The original, the correct, the modified phrase, the check state, the temporary person exclusion record has not changed. The existing production run record is stored in the original run. This folder also includes private parameters and output capabilities, so it's not the model's own public input.

- The original is: **{originals}entries**.
- And the original. 7All the variations are automatic PASS groups: **{complete}Case family**.
- 7Original that does not meet the full transformation PASS requirements: **{incomplete}entries**It keeps the failures and missile launches in their original state.
- The experimental input selector re-verifies the current manufacturing status, excluding people, inspection, inspection hash, and sets the 7We select only the modified PASS group.
- Automatic PASS is different from human approval or meaningful confirmation.

## File roles and reading order

1. `prepared-results.json`: Source run·manifest hash, copy file full hash, auto-completed group ID and scope.
2. `manifest.json`: Selection policy · row count · status · exclusion reason · file hash.
3. `00-input.json`: Original Q/C and private reference answers; accuracy; foreign language classification.
4. `01`~`07` Type JSON: Create Q/Cs connected to the same ID and automatically check status and transition records. Link to ID instead of row location.
5. `export-log.json`, `SOURCE-README.md`If there is, `revisions/`: source summary; consolidated records and original guidance documents.
6. `events.jsonl`This transmission record. No model call.

The line. `source`, `result`, change the power-to-state reference path by interpreting the source run or the source manifest by the run specified. The data folder does not change the path parameters. The private external knowledge classification, correctness, variable label output records are not transmitted to the target model.

## The connection between the creation and experimentation

```shell
PYTHONPATH=src .venv/bin/python -B -m finarch.dataset.03-release.export_run_results \
  {source_run} --prepared-output {output}
```

It's just going to be in a new folder, and it's not going to cover up the existing folder. `evaluation.schedule.dataset.source_run`The production capacity, `results_path`And this is the delivery folder, `input_path`This is a folder `00-input.json`The experimental preparation and practice is the `finarch.experiments.pipeline`If the current source and the forwarding hash are different, it stops before calling.

## Check the screen.

[Source created by Viewer](http://127.0.0.1:8893/?run={run_name})In the actual case, the biological, the examiner, the person's assessment.](http://127.0.0.1:8894/)In any case, select experiments-run to verify that the existence of this folder does not mean that the experiment is running complete.

ReadME is a `src/finarch/documentation/templates/prepared-generation-results.md`It's generated from.
