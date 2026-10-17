# EA reversal review small verification

Status **{status}** · Completed response **{completed}/6** · true **{inverse_true}** · false **{inverse_false}** · Review error **{errors}**.

The existing EA text 6Copy that. **Just call back the review.** It's not a new execution that creates a sentence or re-verifies the manufacturing process. `source_reuse`So, we're going to show you the source of the copy.

- The model: `luna-low-api` · `gpt-5.6-luna` · Logic low. Operating the existing G03 I follow the verification profile.
- New call up 6Turn, automatically re-set, and 0The model only delivers two Q/C fields after deletion.
- The existing taxation case 3The existing EA, which lacks the information. 3The result is an LLM judgment, not an accuracy measurement.

In order of reading:

1. `pilot-selection.json`: real source path; hash; problem / type.
2. `pilot-results.json`, `summary.json`: Individual reverse assessing and maintenance of manufacturing status.
3. `02-generation/01-round/test-xxxx/<EA>/03-validation/07-ea-inverse-review/attempt-001/`The following are the steps: Prompt response, schematic response, raw response, usage, test, judgment.
4. `logs/`Local checks and small call output. `api-usage/summary.json`The actual token is the expected cost, and the invoice is not the fixed value.
5. `verification.json`: Original hashing; identification judgment maintenance; use mark inspection and actual screen check recording.

This run from the Common Viewer → EA type → `03-validation` Or `05-human-review`The text base is yellow, and the restore is shown in the star box. This does not mean that the phrase audit was done newly in this run.

Python testing related 56It passed the items, the mark-up JavaScript test, and the document linking test. The actual call assessment is not a measurement of accuracy, and the person checks whether the statement is based on the text and the validity of the statement. The entire test in the formulation still has previous data paths, model default values, and misstatement role issues, so it doesn't mean the entire project has passed the test.

When you repeat the verification of the storage data, `PYTHONPATH=src .venv/bin/python -m finarch.dataset.checks.ea_inverse_review_pilot --output reports/run/20261001-ea-inverse-review-pilot --verify-only`This command does not make model calls.

[People review screen capture](screenshots/g05-inverse-review.jpg) · [Real screen check in](viewer-verification.json)
