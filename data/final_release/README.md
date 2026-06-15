# FInject Final Release Data

This folder contains the final 426-instance FInject release used by the submitted CIKM 2026 paper.

## Files

- `finject_final_426.jsonl`: one JSON object per line. This should be the primary file for loading and Hugging Face upload.
- `finject_final_426.json`: the same rows as a JSON array.

## Counts

- Total rows: 426
- Source seed problems: 78 answerable FinanceReasoning hard problems
- Categories: 6
- Rows per category: 71

| Category | Rows |
| --- | ---: |
| EA-partial | 71 |
| EA-full | 71 |
| SA | 71 |
| IC-value | 71 |
| IC-source | 71 |
| IC-premise | 71 |

Generator distribution:

| Generator | Rows |
| --- | ---: |
| Claude Opus 4.7 | 108 |
| Gemini 2.5 Pro | 108 |
| GPT-5.5 | 106 |
| R1-Distill-32B | 104 |

## Core Fields

- `sample_id`: unique release instance identifier.
- `source_qid`: original FinanceReasoning problem identifier.
- `category`: perturbation category.
- `generator_model`: model family that generated the perturbation.
- `question`: original question.
- `original_context`: answerable original context.
- `perturbed_context`: final unanswerable context.
- `origin_ground_truth`: answer to the original control problem. Most rows are numeric, while one upstream control has a boolean answer.
- `origin_python_solution`: executable reference solution used to identify answer-critical evidence.
- `gold_label_solvable`: always `false` for final unanswerable variants.
- `gold_label_category`: target perturbation category.
- `stage1_pass`, `stage2_final_pass`, `stage2_strict_final_pass`: automatic validation metadata.
- `repair_status`, `manual_final_repair`: human verification and repair provenance.

## Public Release Note

`schema.json` and `splits.json` are generated from the final release files. The dataset card states the upstream FinanceReasoning dependency and the current license/redistribution status.
