# {{title}}

{{current_intro}}

The completed diagnosis of existing raw responses is preserved in the [problem and improvement plan](../../../../docs/02-experiments/04-comparison/01-improvement-plan.md) and [review evidence](03-research/intent-review-evidence.json). Responses {{review_responses}} selected from {{review_cases}} originals are linked to hashes of {{review_files}} evidence files. Generating this report itself makes **0 new model calls**.

Distinguish the previous response format (file identifier `FinancialAnswerMagnitudeV4`) from the already revised format (file identifier `FinancialAnswerV6`; {{successful}} new responses returned by the provider). These identifiers distinguish response contracts in files; they are not model versions or the sixth experiment. The headings below call them the previous and revised formats. Saving a change and passing local checks is separate from demonstrating an improvement in actual model responses.

{{run_status}}

## Reading order

For numerical summaries, use the [overview dashboard](http://127.0.0.1:8895/dashboard/01-overview/) and [case analysis dashboard](http://127.0.0.1:8895/dashboard/02-explorer/). They connect scatterplots, tables, and actual responses; their scope is documented in the [implementation and reading guide](../../../../viewer/dashboard/README.md).

1. [Problem and improvement plan](../../../../docs/02-experiments/04-comparison/01-improvement-plan.md): previous experiment issues, limitations of the changes, and proposed follow-up review.
2. [Review evidence](03-research/intent-review-evidence.json) and [work report](REPORT.md): raw responses, quotations, hashes, completed scope, and unverified items.
3. [Existing Luna response analysis](01-baseline/analysis.md) and [actual cases](01-baseline/cases.md).
4. [Paper comparison axes and matched pairs](03-research/analysis.md).
5. [Experiment flow](../../../../docs/02-experiments/README.md): definition → input → requests/calls → validation → comparison.
6. [A100 snapshot](02-a100/README.md).
7. [{{run_link_label}}](../../experiments-run/{{run_id}}/README.md): frozen requests, saved states, and actual call records.

## File responsibilities

| Path | Role |
| --- | --- |
| `status.json` | Work state, new run location, and usage-preservation criteria. |
| `api-blocker.json` | Historical API blocking record for exp-004; distinguish it from the new run's current state. |
| `01-baseline/` | Raw responses using the previous format and supplementary exp-004 comparisons; previous scores are preserved. |
| `02-a100/` | Remote reports imported read-only, with paths and hashes. |
| `03-research/intent-review-evidence.json` | Reviewed raw responses/questions, quotation-match observations, and evidence-file hashes. |
| `03-research/` | Intent/response review, P0/P1 pairs for the same original, and reasoning-condition differences. |
| `04-validation/` | Local checks, code/document inspection, and screen verification records. |
| `quota-evidence.json`, `quota-preflight.json` | Previously saved quota queries and execution conditions; no new query was made for this review. |
| `documentation.json` | Current document/report index read by the shared viewer. |
| `events.jsonl` | Report-update and work-state events. |

Select this run in the [shared viewer](http://127.0.0.1:8895/?run=20260923-experiment-improvement) to read the actual latest files. No per-result-folder HTML is generated. Inspect collection and unexecuted states for `{{run_id}}` in the same [experiment viewer](http://127.0.0.1:8894/?run={{run_id}}&tab=overview).

Providing both prompts with a common JSON structure aligns presentation conditions; it does not establish that the structure has zero effect on model behavior. Distinguish already saved changes from proposed new fields or follow-up comparisons. Judge actual effects only after successful responses are available.

This README is generated from `src/finarch/experiments/02-analysis/legacy/comparison/improvement-report-template.md`. Rebuild the report with `PYTHONPATH=src .venv/bin/python -m finarch.experiments.02-analysis.legacy.comparison.improvement_report`. Agent file/screen inspection and completed user review remain separate.
