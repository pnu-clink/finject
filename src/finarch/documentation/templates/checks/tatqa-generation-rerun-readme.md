# {run_name} · TAT-QA Generation is renewable

`{source_run}`The preparation is independently copied and generated as a current prompt. 7So this is a new type. {input_count}In the following paragraphs, the following paragraph is inserted: {approved_count}This is the first case. 7Type is = {variant_count}This is the subject of the existing FAIL. {rejected_count}The failure record of the case is maintained. Preparation's raw response ·date is a record of previous executions and no new model calls.

## Running program

```shell
PYTHONPATH=src .venv/bin/python -u -B -m finarch.dataset.02-generation.generate_schedule \
  --run reports/run/{run_name}
# Change to existing scheduler to plan → generate sentences → verify → fail feedback → process the person review data.

PYTHONPATH=src .venv/bin/python -u -B -m finarch.dataset.03-release.export_run_results \
  reports/run/{run_name}
# After the end of Generation, we'll match the latest numerical results to JSON by type.
```

`start-generation.sh`It calls these two programs in turn, only when you restart the discontinued Generation. `start-generation.sh --resume`It doesn't create any new Python reusable program.

## Models and Objects

The actual model is the same as the previous request. **gpt-5.6-luna / max / API**It's in the run. `hyperparameter.json`and `codex-profiles.toml`We've specified the exact version of the file. We're using the same model for phrase creation, completion verification, EA regression review, error feedback. 200Type, synchronized processing 5The maximum. 3The car, the power supply. 32,768Token, total token budget 500,000.

The past generation has been 9,332The cache-free call applied to the stored tokens and project units is approximately $250,000.27.64This time, we're looking at EA's reviews and reviews. 10,000~12,000Round and round. **$30~60**It's an estimated amount, not an actual bill or a limit on expenditure.

Additional sentences in IC-RELATION use a current logic format that is generated in independent stages after the last row of the table. Whether EA is reversible is recorded with the basis and whether it fails alone. The existing source run and concat annotation are not corrected.

## Reboot before reboot 2026-10-03

Fix the input connection-number tag error found in the first run and then run the data. `restart-history/001-reference-metadata-handoff/`The correct metadata of the task input is missing. 1The building is complemented by a memory from the same ID. `December 28, 2018`I don't read numbers. `1,609,000` It's the same amount as the existing registration number rule, and it doesn't change the original, pre-preparation, correct answer.

`reference-handoff-repair.json`In some cases 668The correct answer to the connection test, `relation-numeric-repair.json`In some cases 668entries ·1,427Pre-testing the items input numbers and actual errors 2I recorded the plan after the building was repaired. 22The items has passed. It doesn't mean that the first interrupt doesn't have the storage, but it doesn't imply that the call that you've already started doesn't already have the call.

## The order of reading and the screen

1. `sequence-status.json`: Running / joining / shutting down state.
2. `terminal.log`, `02-generation.log`, `03-export.log`: Actual output and error of existing programs.
3. `preparation-reuse.json`: Copy file hash, Preparation PASS/FAIL list.
4. `model-preflight.json`, `authorization.json`, `prompt-code-snapshot.json`: Call before model; schema; range of requests and source hash.
5. `02-generation/*-round/progress.json`, `02-generation/summary.json`: Characterized processing and latest type judgement.
6. After you're done. `completion-report.json`, `phase-reports/generation/`, `results/00-input.json`and 01~07 JSON by type.

[common dataset viewer](http://127.0.0.1:8893/?run={run_name})In the original Python graph, check the new sentence verification basis. Automatic PASS and human judgement are separate. Final selection is Preparation PASS + latest 7All types have automatic PASS + no explicit Reject and person Accept is not a requirement.

ReadME is a `documentation/templates/checks/tatqa-generation-rerun-readme.md`It's generated from.
