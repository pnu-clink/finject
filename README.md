# FInject: Expanding Finance Reasoning Problems through Injection of Unanswerability

This directory is the local staging area for the public FInject artifact release.
It is intended to become the GitHub repository that accompanies the CIKM 2026
Resource Track submission.

## Current Contents

- `data/final_release/`
  - `finject_final_426.jsonl`: primary machine-readable release.
  - `finject_final_426.json`: JSON convenience copy.
  - 426 unanswerable variants, balanced as 6 perturbation categories x 71 rows.
- `data/original_controls/`
  - `finject_original_controls_78.jsonl`: 78 answerable original controls for paired evaluation.
  - `finject_original_controls_78.json`: JSON convenience copy.
- `paper/`
  - `main.pdf`: submitted paper PDF copied from the final Overleaf project.
  - `supplementary.pdf`: supplementary material PDF copied from the final Overleaf project.
  - `overleaf_source/`: local copy of the submitted TeX source, figures, and tables. Unused local table archives are intentionally excluded.
- `prompts/`
  - final perturbation-generation, semantic-judge, and answerability-evaluation prompt templates.
- `scripts/`
  - lightweight dataset validation script.
- `examples/`
  - minimal dataset loading example.
- `stage1/`
  - deterministic structural validation reference code. Raw Stage 1 inputs, result exports, and audit workbooks are intentionally excluded.
- `stage2/`
  - placeholder for semantic judge protocol/code organization.

## What Should Go into the Public GitHub Repo

Track:

- final dataset copies under `data/final_release/`;
- paper PDFs and submitted TeX source under `paper/`;
- prompt templates for perturbation generation, semantic judging, and answerability evaluation;
- minimal scripts for loading the dataset, validating schema/counts, scoring model outputs, and reproducing table metrics;
- documentation: dataset card, schema, citation, upstream license check, limitations, ethics, and release notes.

Avoid tracking:

- API keys, `.env`, raw local logs, `.DS_Store`, `__pycache__`, local package caches;
- temporary retry files and failed model outputs unless explicitly documented as audit artifacts;
- raw annotator workbooks with private notes or personal information;
- large build artifacts that are not necessary for reproducibility.

## Immediate TODO Before Public Release

1. Add `LICENSE` after confirming the upstream FinanceReasoning redistribution terms.
2. Review `CITATION.cff` once the final DOI and repository URL are fixed.
3. Review `DATASET_CARD.md` after choosing the final data license.
4. Add `scripts/score_outputs.py` or document which existing scoring script should be used.
5. Create the GitHub repository, then mirror the dataset-facing files to Hugging Face and mint a DOI through Hugging Face or Zenodo.

## Upstream License Status

FinanceReasoning is publicly available on GitHub, but no explicit license file or GitHub-detected license was found during the 2026-06-15 check. See `UPSTREAM_LICENSE_CHECK.md`. Until this is clarified, keep `LICENSE_PENDING.md` and avoid describing the data as openly licensed.

## Sanity Checks

```bash
python3 scripts/validate_dataset.py
python3 examples/load_dataset.py
```
