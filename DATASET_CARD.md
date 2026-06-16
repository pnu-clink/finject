---
language:
  - en
task_categories:
  - question-answering
  - text-classification
  - text-generation
pretty_name: FInject
size_categories:
  - n<1K
---

# FInject Dataset Card

FInject is a financial unanswerability benchmark built by transforming answerable financial reasoning problems into controlled unanswerable variants. Each row preserves the original question and pairs an answerable original context with a perturbed context that is no longer sufficient to support a unique answer.

## Dataset Summary

- Seed source: 78 answerable hard problems from FinanceReasoning.
- Final release size: 426 unanswerable variants.
- Original controls: 78 answerable controls for paired evaluation.
- Balance: 6 perturbation categories x 71 rows.
- Generator families: Claude Opus 4.7, GPT-5.5, Gemini 2.5 Pro, and R1-Distill-32B.
- Validation: deterministic Stage 1 structural validation, non-self Stage 2 semantic judging, balanced sampling, human verification, and repair/regeneration.
- GitHub repository: https://github.com/pnu-clink/finject
- Hugging Face mirror: https://huggingface.co/datasets/pnu-clink/finject

## Intended Tasks

1. **Answerability detection**: decide whether a financial reasoning instance is answerable from the provided context.
2. **Perturbation-type prediction**: classify why the instance is unanswerable.
3. **Rationale generation**: explain the missing or conflicting evidence that prevents a unique answer.

## Perturbation Categories

| Category | Description |
| --- | --- |
| EA-partial | Replace one answer-critical value with `[DATA MISSING]`. |
| EA-full | Remove the carrier clause, sentence, row, cell, or entry containing answer-critical evidence. |
| SA | Silently remove an answer-critical value while keeping the text fluent and marker-free. |
| IC-value | State conflicting values for the same answer-critical quantity. |
| IC-source | Attribute conflicting values to named sources without a reliable priority cue. |
| IC-premise | Add mutually incompatible answer-critical premises. |

## Files

- `data/original_controls/finject_original_controls_78.jsonl`: answerable controls used for paired evaluation.
- `data/original_controls/finject_original_controls_78.json`: JSON-array copy.
- `data/final_release/finject_final_426.jsonl`: primary unanswerable-variant dataset file.
- `data/final_release/finject_final_426.json`: JSON-array copy.
- `data/final_release/schema.json`: field schema.
- `data/final_release/splits.json`: row counts by category and generator.
- `prompts/`: perturbation generation, semantic judge, and answerability evaluation prompts.
- `paper/`: submitted paper and supplementary material.

The same files are mirrored on Hugging Face under
`pnu-clink/finject`. They can be loaded with:

```python
from datasets import load_dataset

final = load_dataset(
    "pnu-clink/finject",
    data_files="data/final_release/finject_final_426.jsonl",
    split="train",
)
```

## Core Fields

- `sample_id`: unique release identifier.
- `source_qid`: original FinanceReasoning problem identifier.
- `category`: perturbation category.
- `generator_model`: generator family.
- `question`: original question.
- `original_context`: answerable original context.
- `perturbed_context`: final unanswerable context.
- `origin_ground_truth`: answer to the original control problem. Most rows are numeric, while one upstream control has a boolean answer.
- `origin_python_solution`: executable reference solution for the original answerable problem.
- `gold_label_solvable`: always `false` for final unanswerable variants.
- `gold_label_category`: target perturbation category.
- `stage1_pass`, `stage2_final_pass`, `stage2_strict_final_pass`: automatic validation metadata.
- `repair_status`, `manual_final_repair`: human verification and repair provenance.

See `data/final_release/schema.json` for the full field list.

## Evaluation Protocol

The main answerability evaluation pairs original answerable controls with final-release unanswerable variants. A model receives only the question and context and must return one of:

```json
{"decision":"INSUFFICIENT_INFORMATION","answer":null}
```

or:

```json
{"decision":"ANSWER","answer":<numeric answer>}
```

Main metrics include original-control accuracy, refusal precision/recall/F1, hallucination rate on unanswerable variants, paired success, and MCScore.

## Limitations

FInject focuses on English financial word problems and controlled single-instance evidence failures. It does not cover real-time market data, multimodal filings, long-document retrieval, or actual financial advice. The perturbations are synthetic and are intended for model evaluation, not decision support.

## Ethics

The benchmark is derived from public benchmark-style financial reasoning problems and synthetic perturbations. It does not contain private financial records. Generative AI tools were used during construction and judging, but final dataset inclusion was subject to validation and human review.

## Citation

If you use FInject, please cite this repository. The proceedings citation will
be updated after publication.

```bibtex
@misc{finject2026,
  title = {FInject: Expanding Finance Reasoning Problems through Injection of Unanswerability},
  author = {Kim, Jinkyu and Kim, Jinsu and Park, Wooik and Sung, Mujeen and Gim, Mogan and Choi, Donghee},
  year = {2026},
  note = {Manuscript and dataset},
  url = {https://github.com/pnu-clink/finject}
}
```
