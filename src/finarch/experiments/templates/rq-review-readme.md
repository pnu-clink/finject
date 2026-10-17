# RQ study interpretation and integration guidance {run}

1. [rq-review.md](rq-review.md): 104findings 9It's the RQ1RQ4 report, which is the top items item.
2. [rq-review-audit.md](rq-review-audit.md): Check the main group of all F's, the support group, the reason for the decision.
3. [rq-review.json](rq-review.json)It's the current editing of the conversation, the definition of RQ, the raw material hash and the entire response chart.
4. [rq-review-validation.json](rq-review-validation.json): 104It's a record of whether all items were assigned to exactly the same group, whether the reference and raw material hash were correct, not meaningful correctness verification.
5. [findings.json](findings.json), [findings.md](findings.md)The existing A03 It's the original. It's traced to the F number on the corresponding chart.

The log leaves the run route in events.jsonl. In the experiment viewer, read this run → study interpretation → RQ individual integrated review.02-analysis/03-research/rq_review.py is responsible for the template, and the new model calls are not performed.
