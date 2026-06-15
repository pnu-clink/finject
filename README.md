# FInject

**FInject: Expanding Finance Reasoning Problems through Injection of Unanswerability**

FInject is a financial unanswerability benchmark for evaluating whether language
models can recognize when a finance reasoning problem does not support a unique
answer. The benchmark starts from answerable FinanceReasoning seed problems and
creates controlled unanswerable variants by removing answer-critical evidence or
injecting irreconcilable conflicts.

The repository contains the dataset, original paired controls, prompt templates,
validation utilities, and the submitted paper artifacts.

## Dataset

| Split | Rows | Description |
| --- | ---: | --- |
| `data/final_release/finject_final_426.jsonl` | 426 | Final unanswerable variants |
| `data/original_controls/finject_original_controls_78.jsonl` | 78 | Answerable original controls for paired evaluation |

The 426 unanswerable variants are balanced across six perturbation categories:

| Category | Rows | Meaning |
| --- | ---: | --- |
| `EA-partial` | 71 | Explicitly mask one answer-critical value |
| `EA-full` | 71 | Remove the carrier clause, sentence, row, cell, or entry |
| `SA` | 71 | Silently remove an answer-critical value |
| `IC-value` | 71 | Add conflicting values for the same quantity |
| `IC-source` | 71 | Attribute conflicting values to named sources |
| `IC-premise` | 71 | Add mutually incompatible premises |

Each final row includes the original question, original context, perturbed
context, original reference answer, executable reference solution, perturbation
category, generator provenance, automatic validation metadata, and human repair
provenance.

## Tasks

FInject supports three evaluation tasks:

1. **Answerability detection**: decide whether the provided context supports a
   unique answer.
2. **Perturbation-type prediction**: identify why an unanswerable instance is
   unanswerable.
3. **Rationale generation**: explain the missing or conflicting evidence.

The main paper focuses on answerability detection with paired evaluation:
models should answer the 78 original controls and refuse the corresponding
unanswerable variants.

## Repository Layout

```text
data/
  final_release/          Final 426-instance unanswerable benchmark
  original_controls/      78 answerable controls for paired evaluation
examples/
  load_dataset.py         Minimal JSONL loading example
paper/
  main.pdf                Submitted paper
  supplementary.pdf       Supplementary material
  overleaf_source/        TeX source used to compile the submitted files
prompts/
  perturbation_generation.md
  semantic_judge.md
  answerability_evaluation.md
scripts/
  validate_dataset.py     Schema and count validation
stage1/
  Deterministic structural validation reference implementation
stage2/
  Semantic judge protocol summary
```

## Quick Start

Load the final release:

```python
import json
from pathlib import Path

path = Path("data/final_release/finject_final_426.jsonl")
rows = [json.loads(line) for line in path.read_text().splitlines()]

print(len(rows))
print(rows[0]["question"])
print(rows[0]["perturbed_context"])
```

Run the included validation checks:

```bash
python3 scripts/validate_dataset.py
python3 examples/load_dataset.py
```

Expected validation summary:

```text
FInject validation passed.
Rows: 426
Source problems: 78
Original controls: 78
```

## Evaluation Format

The answerability prompt expects one JSON object:

```json
{"decision":"INSUFFICIENT_INFORMATION","answer":null}
```

or:

```json
{"decision":"ANSWER","answer":123.45}
```

The main metrics are original-control accuracy, refusal precision/recall/F1,
hallucination rate on unanswerable variants, paired success, and MCScore. The
full answerability prompt is provided in
`prompts/answerability_evaluation.md`.

## Construction Artifacts

- `prompts/perturbation_generation.md` describes the generation and
  human-calibrated re-perturbation prompts.
- `stage1/` provides the deterministic structural gate used to remove malformed
  perturbations before semantic judging.
- `prompts/semantic_judge.md` and `stage2/README.md` describe the non-self
  semantic judging protocol.

Intermediate raw generations, audit workbooks, annotator scratch files, and API
logs are not included.

## Citation

```bibtex
@inproceedings{finject2026,
  title = {FInject: Expanding Finance Reasoning Problems through Injection of Unanswerability},
  author = {Kim, Jinkyu and Kim, Jinsu and Park, Wooik and Sung, Mujeen and Gim, Mogan and Choi, Donghee},
  booktitle = {Proceedings of the 35th ACM International Conference on Information and Knowledge Management},
  year = {2026},
  note = {Resource Track}
}
```
