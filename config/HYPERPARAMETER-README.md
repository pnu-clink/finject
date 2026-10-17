# Reading execution settings

Read `hyperparameter.json` → `codex-profiles.toml` → the run's frozen `config.json`.

For Preparation, Generation, Evaluation, and Analysis, `schedule` defines scope and concurrency; `run` defines model selection and experiment conditions. Model IDs, reasoning effort, and API output limits are defined in profiles. Prices, price-check dates, credential paths, billing explanations, and historical execution records are separate from the hyperparameters.

| Setting | Purpose | Consumer |
| --- | --- | --- |
| preparation.schedule / run | Preparation inputs, concurrency, and purpose-specific models | Dataset schedule_settings.py |
| generation.schedule / run | Variant construction, revision, validation, and concurrency | Dataset schedule_settings.py |
| generation.run.models.ea_inverse_review | Dedicated EA inverse profile: sol61-high-api, gpt-6.1-sol / high; output 32,768 and total limit 500,000 | profiles.py → ea_inverse_review.py → Responses API |
| evaluation.schedule.dataset | Dataset run, source input, original count, and all-seven-variants condition | Experiment settings.py → dataset.py |
| evaluation.run.models | Per-model OFF/ON profiles | settings.py → pipeline.py |
| evaluation.run.transport / cache | Batch execution / cache OFF | openai_batch.py / openai_api.py |
| evaluation.run.seed / definition_source_run | Request-order seed / source run for prompts and schemas | pipeline.py |
| analysis.run.backend | codex or api backend | settings.py → 02_analysis/pipeline.py |
| analysis.run.models | Codex and API profiles | settings.py → 02_analysis/llm_backend.py |
| analysis.schedule / run.technical_retry_limit | Concurrency and timeout / bounded technical retries | 02_analysis/llm_backend.py |

Analysis uses fixed `concurrency=100` and `adaptive.enabled=false`. CPU samples are recorded without increasing the limit. The experiment CLI reads this JSON by default; historical TOML configurations require explicit selection. Existing runs use frozen settings. To change an Analysis model, use `restart-analysis` so earlier results remain preserved.

## Profile selections

| Purpose | Profile | Model / reasoning | Output limit |
| --- | --- | --- | ---: |
| Evaluation · Reasoning OFF | luna6-none-api | gpt-6-luna · none | 65,536 |
| Evaluation · Reasoning ON | luna6-medium-api | gpt-6-luna · medium | 65,536 |
| Analysis · Codex default | sol61-low-cli | gpt-6.1-sol · low | This API option does not apply to the CLI |
| Analysis · API option | sol61-low-api | gpt-6.1-sol · low | 65,536 |

Select `api` or `codex` in `analysis.run.backend` before preparing a new run. A Codex error does not trigger automatic API fallback. Solving requests contain only public Q/C and precision; private data supports E04 numeric comparison and A01 onward.

Both originals and variants use **Unguided Solving / Criteria-Guided Solving × Reasoning OFF/ON**. The two solving instructions are fixed experiment conditions, rather than separate hyperparameter choices. Request manifests record `prompt_condition: unguided` or `guided`. For one model, 10 originals plus 70 variants produce 320 requests; 100 originals plus 700 variants produce 3,200. Historical runs retain their frozen requests and counts.

`max_output_tokens` is an upper bound, not a requested answer length. OpenAI requests do not send `thinking_budget`; reasoning modes use profile `effort`.

## Output-limit history

The retained execution records describe:

| Recorded workload | Initial → retry limit | Observation |
| --- | --- | --- |
| exp-001 case analysis: 800 requests | 12,000 → 32,768 | 203 truncated; 12 truncated among 233 retries |
| exp-001–003 response analysis | 32,768 → 65,536 | Retries also address format/citation failures; a larger limit does not fix every error |
| exp-001–003 Luna solving | 8,192 | No OUTPUT_TRUNCATED in 9,000 saved solutions |
| exp-004 Luna solving | 8,192 | 300 returned and format-valid; definition frozen before the change |

The newer setting uses 65,536 for new requests. Existing configurations, manifests, and raw responses are not changed retroactively. API limits and actual Codex CLI options are distinct.

## Execution and inspection

- Inspect settings: `PYTHONPATH=src .venv/bin/python -u -B -m finarch.experiments.pipeline config`.
- Freeze Analysis: `pipeline configure-analysis --run <run> --config config/hyperparameter.json`.
- Execute Analysis: `pipeline analysis --run <run>`, using the Python entry point above.
- Change a stopped Analysis model: `pipeline restart-analysis --run <run> --config config/hyperparameter.json --authorization '<actual user instruction>'`, followed by `analysis`. Earlier Analysis remains in `02_analysis-history`; Evaluation is not called again.
- Frozen Analysis settings: `02_analysis/config.json`. Actual model, effort, and command: each stage's `calls/*/attempt-*/provider-request.json`.
- Scheduling and CPU samples: `02_analysis/scheduler.json`. Commands and progress: `pipeline.log` and `events.jsonl`.
- Inspect the Evaluation dataset path before preparation. The historical 557-original selection differs from the frozen 291-original TAT-QA cohort.

See [experiment source](../src/finarch/experiments/README.md), [profiles](codex-profiles.toml), and [settings](hyperparameter.json).

`evaluation.run.definition_source_run` is null in the shared file. A new preparation reads the common/Unguided/Criteria-Guided instructions from [experiment prompts](../src/finarch/experiments/prompts/README.md), and the response format from [schemas](../src/finarch/experiments/schemas/json/README.md), then freezes them in the new run. Resumption reads the existing definition.

The shared historical Evaluation selection is 557 originals and 3,899 variants from 20260917-003: 17,824 requests. The subsequent 1,080-original 20260917-002 cohort uses a separate run with matching conditions. Each run freezes its actual configuration.
