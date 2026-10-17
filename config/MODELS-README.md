# Pipeline model selection · 2026-10-01

New calls use `gpt-6-luna` in place of `gpt-5.6-luna` and `gpt-6.1-sol` in place of `gpt-5.6-sol`. Profile IDs, effort, output/total token limits, prompts, and response schemas are retained.

| Workflow / purpose | Selected profile | Model / effort | Output / total token limit |
| --- | --- | --- | --- |
| Preparation: source review and revision | luna-max-api | gpt-6-luna / max | 32,768 / 500,000 |
| Preparation: POT and independent solution | sol-medium-api | gpt-6.1-sol / medium | 128,000 / 500,000 |
| Preparation: semantic verification and exception feedback | luna-max-api | gpt-6-luna / max | 32,768 / 500,000 |
| Generation: realization, completed-text validation, and feedback | luna-max-api | gpt-6-luna / max | 32,768 / 500,000 |
| Generation: EA inverse-recoverability review | sol61-high-api | gpt-6.1-sol / high | 32,768 / 500,000 |
| Shared: failure interpretation and display translation | luna-max-api | gpt-6-luna / max | 32,768 / 500,000 |
| Explicit small tests | luna-low-api | gpt-6-luna / low | 32,768 / 500,000 |
| Evaluation: reasoning OFF / ON | luna6-none-api / luna6-medium-api | gpt-6-luna / none · medium | 65,536 / experiment settings |
| Analysis: A02/A03 defaults | sol61-low-cli / sol61-low-api | gpt-6.1-sol / low | 65,536 / experiment settings |

Since 2026-10-08, EA inverse review has a separate `ea_inverse_review` purpose. Both `generation.run.models.ea_inverse_review` and shared `[selection].ea_inverse_review` select `sol61-high-api`. Inverse true/false and call failures do not alter construction PASS/FAIL. Existing frozen run settings and results are preserved.

Construction profiles are defined in [codex-profiles.toml](codex-profiles.toml). Preparation/Generation `run.models` in [hyperparameter.json](hyperparameter.json) selects a profile for each purpose. Calls outside a schedule use `[selection]`; an explicit per-call `profile_id` takes precedence. Changing only the generic generation/validation selections does not replace every purpose-specific setting. Evaluation/Analysis also resolve `run.models` from the hyperparameters. The default Analysis profile is `sol61-low-cli` (gpt-6.1-sol/low), with fixed concurrency 100. Historical experiment TOML files remain available with an explicit `--config`. Check the run's frozen configuration and `provider-request.json` for actual execution settings.

CLI profiles `luna-none`, `luna-low`, `luna-medium`, and `luna-max-cli` also use `gpt-6-luna`. Other model choices, including Astra, are outside this two-model replacement. Existing `gpt-6-sol` profiles preserve compatibility. Frozen settings, raw responses, and price records are not changed retroactively; requests record the resolved model, effort, and profile hash.

The estimate table retains historical prices and includes entries based on the official [Luna](https://developers.openai.com/api/docs/models/gpt-6-luna) and [Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol) pages used for that update. Missing price tiers remain unknown rather than zero. These are saved estimation settings, not a current billing quote.

The recorded model-selection change was checked through configuration resolution, request creation, local response substitutes, and export regression checks. It did not include paid model calls or a measured improvement in semantic quality.
