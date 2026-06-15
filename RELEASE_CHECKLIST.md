# CIKM 2026 Public Release Checklist for FInject

This checklist translates the CIKM 2026 Resource Track guidance into concrete release tasks for the FInject repository and Hugging Face dataset page.

Official references checked on 2026-06-15:

- CIKM 2026 Resource Papers: https://cikm2026.diag.uniroma1.it/resource-papers/
- CIKM 2026 Submission Policies: https://cikm2026.diag.uniroma1.it/submission-policies-and-information/

## CIKM Requirements That Matter

- Resource papers are limited to 4 pages, including appendices and acknowledgments, plus unlimited pages for references and the GenAI Usage Disclosure.
- Supplementary materials may be cited if they are accessible through online platforms such as GitHub. Reviewers may choose whether to inspect them.
- Dataset and benchmark papers must publish datasets and metadata through a dataset-sharing service that provides a DOI, such as Zenodo, Datorium, Dataverse, or another indexed service.
- The resource should be available, well documented, ethically described, and reusable by most academic and industry researchers.
- Code resources should be publicly available through GitHub, GitLab, Bitbucket, or a similar platform, with dependencies, limitations, and documentation.
- The resource should explain provenance, preprocessing, cleaning, aggregation, annotation, and how the dataset follows FAIR principles.

## Recommended Public Layout

Use GitHub for code, protocols, and reproducibility. Use Hugging Face for the dataset-facing artifact. Use Zenodo or the Hugging Face DOI integration for a DOI.

### GitHub

Recommended top-level files:

- `README.md`: concise project overview, paper link, dataset link, DOI, quickstart, citation, license, contact.
- `LICENSE`: explicit code/data license. Use a permissive code license only if the upstream FinanceReasoning terms allow it. If source-data redistribution has constraints, separate code and data licenses.
- `CITATION.cff`: citation metadata for GitHub and Zenodo.
- `DATASET_CARD.md`: copy or mirror the Hugging Face dataset card.
- `requirements.txt` or `environment.yml`: minimal reproducible environment.
- `.gitignore`: exclude API keys, local logs, `.DS_Store`, LaTeX build artifacts, and raw private annotation workbooks if not intended for release.

Recommended directories:

- `data/`
  - `finject_final_426.jsonl`
  - `finject_final_426.json`
  - `schema.json`
  - `README.md`
- `prompts/`
  - `perturbation_generation.md`
  - `semantic_judge.md`
  - `answerability_evaluation.md`
- `scripts/`
  - `validate_dataset.py`
  - `evaluate_answerability.py`
  - `score_outputs.py`
  - `compute_human_agreement.py`
- `examples/`
  - `load_dataset.py`
  - `run_small_eval.py`
- `paper/`
  - `main.pdf`
  - `supplementary.pdf`

Do not publish intermediate scratch artifacts by default: raw API logs, failed retries, local `.bak` files, archived HTML annotation tools, local `.env`, or unredacted workbooks with annotator-identifying notes. If annotation evidence is released, publish normalized JSON/CSV summaries and reason-code distributions rather than every raw working file.

### Hugging Face Dataset

Recommended files:

- `README.md`: Hugging Face dataset card with YAML metadata.
- `finject_final_426.jsonl`: primary dataset.
- `finject_final_426.json`: optional convenience copy.
- `schema.json`: field definitions and types.
- `splits.json`: row counts by category and generator.
- `prompts/`: the three final prompt templates or links to GitHub.
- `paper/`: `supplementary.pdf` and optionally `main.pdf` if distribution is allowed.

Dataset card sections:

- Dataset summary: 78 answerable seed problems and 426 controlled unanswerable variants.
- Task formulation: answerability detection, perturbation-type prediction, rationale generation.
- Data fields: `sample_id`, `source_qid`, `category`, `generator_model`, `question`, `original_context`, `perturbed_context`, `origin_ground_truth`, `origin_python_solution`, `gold_label_solvable`, validation votes, sampling metadata, repair provenance.
- Splits and counts: 71 rows per category; 426 total unanswerable variants.
- Provenance: derived from FinanceReasoning hard problems; explain selection, perturbation, Stage 1, Stage 2, human verification, repair.
- Annotation process: two-axis category validity and unanswerability labels, agreement summary, reason-code families.
- Evaluation protocol: answerability prompt, output schema, metrics.
- Limitations: English finance word problems, synthetic single-instance evidence failures, not financial advice, no real-time market data, no multimodal filings.
- Ethics: public benchmark source, synthetic transformations, no private financial records, GenAI-assisted construction with human review.
- Licensing: state code and data licenses separately and mention upstream dataset constraints.
- Citation: CIKM paper and DOI.

## Supplementary Material Strategy

Keep `supplementary.pdf` as a compact audit document, not as the only source of reproducibility. It should contain:

- Stage 1 deterministic validation pseudocode and accounting audit.
- Stage 2 semantic judge protocol and output schema.
- Perturbation generation prompts, including category-specific instructions.
- Human-calibrated re-perturbation prompt.
- Answerability evaluation prompt.
- Metric formulas.
- Human annotation summary and full agreement table.
- Detailed experiment tables and representative hallucination cases.

Also publish the underlying machine-readable artifacts in GitHub/Hugging Face. This matters because CIKM's resource rubric asks whether the resource is available, documented, reusable, and whether provenance and preprocessing are clear. A PDF alone is weaker than a PDF plus dataset card plus runnable scripts.

For review-time or camera-ready upload, use this order of preference:

1. Main paper cites GitHub/Hugging Face/DOI links.
2. If EasyChair allows supplementary upload, attach `supplementary.pdf` as an optional supplement.
3. Ensure the uploaded `supplementary.pdf` matches the repository version.
4. After acceptance, archive GitHub/HF release on Zenodo or enable a DOI-backed dataset release, then update camera-ready links.

## Immediate Cleanup Tasks

- Keep the root `README.md` FInject-centered and remove earlier exploratory taxonomy language.
- Keep public dataset files under the `finject_*` naming convention.
- Add `schema.json` for the final 426-row dataset.
- Add a dataset card and citation file before creating the DOI snapshot.
- Keep the internal final construction artifact as the source of truth, then export a clean public copy under `data/`.
- Publish final prompt templates from the supplementary material under `prompts/`.
- Publish only final downstream summaries and scoring scripts, not temporary logs or worker packages with local paths.
