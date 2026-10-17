# Generation by Generation

`01-perturbation` Change the graph. Check the calculation `02-generate-text` The actual request, the response, the edit check `03-validation` Fixed meanings check `04-human-review` It's the final person review sequence.

Only the failed type and the changed dependent type are shown in the next graph. The previous graph's pass record keeps the source. 1The verified IC-VALUE front, Type 2The IC-VALUE is a condition pair that places the same generated phrase in front and back.

The supplementary instructions are for each of the variables `Article/type/feedback`Save separately and add only the same case-type generating call of the next variable. `00-evidence.json`The basis for failure, `02-result.json`The complementary content of the next graph `feedback/01-applied.json`The actual application source and hash is the check prompt does not change during the hash. `final-validator.json`The silver jacket records the cause and whether it is.

In the common viewer, if you select run, factor, problem, pattern, step, you read the actual saved file. The empty step is a misspoke. Run command, start, finish, search time is left in logs of timing.json and similar structures.

QI01 The policy is basically off. `ea_recovery_policy.enabled=true`The plan is to `recovery_preview`And the final chapter of the `03-validation/05-recovery-screen.json`The final file contains the check text hash, event identification information, recovery mode, and user location. RECOVERABLE/UNKNOWN blocks any Python quality gate and does not re-interview the LLM handler. The existing PASS and the entire EA review of audit v3 are preserved. Currently, the relationship between the two registered grammar is UNKNOWN, and the subject accounting is not yet done. The resulting file tree can read sidecar and does not create any viewer screen.

## Parallel processing record
Preparation is the parallelism.preparation of config.json 10), Generation is parallelism. 2The next generation type runs two types of Source and maintains the case position until the end of Source. The VALUE front and back share the same additional phrases. Current state in queue.json, change dynamics in queue .jsonl, progress.json and results in each type run.json. The standby state is displayed above the viewer's variable summary.

Article: Feedback generation by type parallelism.feedback 3The same case/type of duplicate input is rejected and the completed feedback is reused. 2And keep it that way.
