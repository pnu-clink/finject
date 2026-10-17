# EA type label unification

State of play: {status}

|The existing identifier|Current identifier|Meaning|
|---|---|---|
|EA_02 / EA-02|EA_01 / EA-01|Delete the front input|
|EA_03 / EA-03|EA_02 / EA-02|Delete the back input|

It's changing with a single simultaneous mapping. `EA 01 / EA 02` The mark and the `06-ea-earlier-input / 07-ea-later-input` The saved folder keeps it. It doesn't re-create the calculation, the judgment, the judgment costs or call the LLM.

## Reading order

1. `completed.json`, `final-integrity.json`: Final file contrast and finished result. `status`Check that it's verified/complete.
2. `changes.jsonl`SHA2 before and after the change of the original location of each file.56In progress, the chief of staff `finish.sqlite`.
3. `finish-labels.log` → `finish-readmes.log` → `finish-hashes.log`It keeps the records that were intentionally stopped and then executed.
4. `recovery-tests.log`, `regression.log`, `viewer-tests.log`, `syntax-check.log`The final results are confirmed with the following condition:
5. `originals-recovered.zip`, `additional-originals/`: Normal restored existing backups and additional originals. `originals.zip`And it preserves it.
6. `interruption-check.json`, `staged-audit-summary.json`It's the first breakdown test, and it's the final finish.
7. `summary-label-check.json`, `workbook-validation.json`: main run counterparts and axes 14items testing: The count of JSON in summary is the number of fields that appear in the overlay record, not the number of cases.
8. `concurrent-changes.json`: Change the other task found in the final contrast; move the folder 7The data and the verification basis.
9. `viewer-verification.json`, `viewer-label-mapping.log`: Verify the connection to the actual common viewer and EA save path.
10. `delegated-originals.json`, `delegated-originals.zip`: The original before the change was sent to the task of the experimental folder 2,177G. The experimental folder movement and labeling implementation doesn't verify anything in the work.

Git, the database, the integrity, the distinction, worktree preserves. `reports/feedback-011-017`It also maintains the already normal type classification, and only maps the previous label of the internal source log. You need to first check the subsequent changes and the paths that have been moved for other tasks when you restore the backup.

Common viewer: [FinanceReasoning](http://127.0.0.1:8893/dataset/?run=20260917-002), [TAT-QA](http://127.0.0.1:8893/dataset/?run=20260917-003)It reads the latest data stored when the server runs.

{details}

Security and accountability order: [EA label and interruption recovery](../../docs/77-ea-label-migration.md).
