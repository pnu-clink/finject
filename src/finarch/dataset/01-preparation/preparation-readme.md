# Preparation: original-item review

`reference-data.json` is the reference before correction; `data.json` is the current validated working data. `data-comparison.json` records the changed locations in Q, C, and A. The viewer displays the reference on the left and current data on the right. Source material is preserved, and this stage's human-review workflow does not hand off data before approval.

Reading order: `01-source` for source text and provenance → `02-review-and-correct` for source checks → `03-calculation` for code and reference-answer comparison → `04-graph` for the computation graph → `07-human-review` for human decisions.

A failed source review prevents calculation. Automated success is separate from human approval. In this review workflow, all selected cases must finish human review before approved material is passed to Generation. Changes after approval require review again. Consult the top-level Dataset runbook for the current scheduler's entry gate.

`run.json` records case state; `events.jsonl` records execution events. Missing stage outputs mean the stage has not run. Source data and raw model responses are never overwritten.
