# QI02 Prepare to enter the original baseline {run_id}

Source text {originals}items → frozen transformation {variants}Connect the items, get ready. {prepared}items · incomplete {not_prepared}Sources are from FinanceReasoning. {FinanceReasoning}, TAT-QA {TAT_QA}. **Call the actual Qwen baseline0· Reviewing the purpose0**And it doesn't interpret the preparation to be the experiment.

## Reading order

1. `summary.json`Unit: the elementary92Come on, change it up.624So we're going to divide it into.
2. `public/dataset.json`There's only an id/context/question for model input. The source code is the approved Preparation C/Q that created the variant and it distinguishes it from the raw provider code.
3. `public/requests/<case>.json`The real stored: 624Model/system/schema/temperature0/max_tokens4 that has been identified in the items request096I just put the original Q/C. No network transmission.
4. **Private** `private/originals.json`Reference/gold: source: authentication parameters: source/working hash: case-by-case derivative variant connection: NOT_REVIEWED: misrepresented reason: not sent to the model with public input.
5. `manifest.json`: input hash is variable verification and public output hash. `sidecar-schema.json`The private report, `public-input-schema.json`It's a real JSON Schema of public input.
6. `events.jsonl`, `checks.txt`It's the production stage and the local test results.

From a common viewer. `{run_id}`The screen reads the private report for the researcher, so it's not a public distribution screen. GET doesn't analyze, write, model calls. Public/private is the file and request boundary, and it doesn't mean an OS access barrier.

## Supply restrictions

5The items-review meanings are also left in this minimum range as NOT_REVIEWED. 0017 The meaning of operating income/charges does not extend the complexity issue to a complete misconfirmation or new judgment. gold is separate from the verification basis.

The Qwen baseline was saved to preserve ongoing experiments and comparison conditions. The storage model alias alone didn't confirm the distribution revision. 4~6The re-quality API test is not a replacement for the Qwen baseline.

## Re-creation

`PYTHONPATH=src .venv/bin/python -m finarch.dataset.03-release.original_baseline --source reports/run/20260916-001 --quality-root reports/run/20260916-quality-v1 --output reports/run/new-factoring`

The existing output rejects. The overwrite variant: incorrect parent; resource hash/coefficient/QC inconsistency does not pass, and some uncertain sources preserve the reason NOT_PREPARED. It uses the public field allowlist and the private value change request variable check, and does not remove the random number by pressing the same correct answer in the text.
