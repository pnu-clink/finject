# FInject Original Controls

This folder contains the 78 answerable original controls paired with the FInject final release.

## Files

- `finject_original_controls_78.jsonl`: one answerable control per line.
- `finject_original_controls_78.json`: the same rows as a JSON array.

## Why These Controls Are Included

The main FInject evaluation uses paired instances: a model should answer the original control when evidence is sufficient and refuse the corresponding unanswerable variant when evidence is missing or conflicting. Providing the 78 controls makes the paired evaluation reproducible without requiring users to reconstruct the seed subset manually.

## Upstream Provenance

The controls are derived from the public FinanceReasoning benchmark. The full upstream FinanceReasoning dataset is not redistributed here. See `../../UPSTREAM_LICENSE_CHECK.md` and `../../LICENSE_PENDING.md` before public release.

## Core Fields

- `control_id`: FInject control identifier.
- `source_dataset`: upstream dataset name.
- `source_qid`: upstream FinanceReasoning problem identifier.
- `question`: original answerable question.
- `original_context`: original answerable context.
- `origin_ground_truth`: answer to the original control problem. Most controls are numeric, while one upstream control has a boolean answer.
- `origin_python_solution`: executable reference solution.
- `gold_label_solvable`: `true`.
- `paired_unanswerable_categories`: categories available for the same source problem in the final release.
