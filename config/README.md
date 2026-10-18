# Configuration and credentials

All commands run from the repository root. Install dependencies using the [root guide](../README.md#installation-and-credentials). The submission contains no real `.env` or API key.

## Credential loading is pipeline-specific

Copy `.env.example` to `.env` and fill only the variables needed by your chosen providers. Use literal `KEY=value` assignments. Do not use shell commands, variable expansion, or command substitution. `.env` and `.env.*` are ignored by Git; `.env.example` is the blank public example.

| Workflow / transport | Credential source |
| --- | --- |
| Dataset OpenAI calls | `OPENAI_API_KEY` in the process environment first, then the repository-root `.env`. Missing credentials raise `OPENAI_API_KEY_MISSING`. |
| Evaluation with the profile-based OpenAI config | `OPENAI_API_KEY` in the root `.env`; the resolved config sets `key_file` explicitly. An environment key does not override this file. |
| API Analysis with the profile-based config | The same explicit `.env` key file, for the separately selected Analysis model. |
| Other experiment JSON configurations | Use their `key_variable` and `key_file`. If `key_file` is absent, the provider reads the process environment only. |
| Anthropic API | The current adapter expects `CLAUDE_API_KEY` and a configured `workspace_id` beginning `wrkspc_`. |
| Gemini / Orca | `GEMINI_API_KEY` / `ORCA_API_KEY`, only when their provider configuration is selected. |
| CLI backends | Installed provider CLI and its own login/session. API keys alone do not establish CLI authentication. |

The experiment key-file parser rejects empty or nonliteral assignments. A missing file can raise `FileNotFoundError`; missing variables and unset environment keys have separate errors. Never print or share key values. Configuration/prepare commands do not test the validity or billing status of a credential.

## Dataset configuration

- `source-catalog.json`: four pinned source files, hashes, URLs, commits, and adapters. Paths are relative to the catalog.
- `llm.json`: runtime enablement, role capabilities, timeout, and `profiles_path`. It currently has `execution_enabled: true`; actual execution is not an offline check.
- `codex-profiles.toml`: model transport, model ID, reasoning effort, and output budget.
- `hyperparameter.json`: Preparation/Generation schedules, purpose-specific model profiles, rounds, retry settings, and shared API concurrency. Current API concurrency is **200**. Current Preparation planning resolves most roles to `gpt-6-luna` / `max`, and Python-solution generation to `gpt-6.1-sol` / `medium`. Inspect the plan for the exact current mapping; Generation has its own role mapping.

Keep `llm.json`, `codex-profiles.toml`, and `hyperparameter.json` together and run `--plan-only` to inspect the resolved settings. Custom `hyperparameter_path` values are not applied consistently across scheduling and model selection; moving only one configuration file can select unintended settings.

## Evaluation and Analysis configuration

Use [experiments/reviewer-smoke.toml](experiments/reviewer-smoke.toml) for a small experiment with one supplied final-data family and concurrency one. Inspect the resolved configuration with `pipeline config` before preparing a run. Your account must support the selected models for live execution.

Pass `--config` explicitly when using the supplied final data. The CLI default is `config/hyperparameter.json`. In other configurations, set the dataset and credential paths to files available in your checkout; `experiments/config.toml` expects `data/generated/20261003-003`.

The smoke configuration prepares 8 inputs × 2 prompt conditions × 2 reasoning modes = 32 Evaluation requests. Its Evaluation model is `gpt-6-luna` with `none`/`medium` reasoning. API Analysis is separately configured as `gpt-6.1-sol` / `low`.

**Analysis compatibility:** the supplied `gpt-6.1-sol` API profile is rejected before Batch submission by the current cache policy (`TRANSPORT_NO_VERIFIED_PROMPT_CACHE_DISABLE_CONTROL`); adding an API key does not change this. Codex Analysis uses a separate backend: select `analysis.backend = "codex"`, configure its model profile, and provide an installed Codex CLI logged in with ChatGPT. This Analysis backend does not apply the target-model Evaluation cache-disable gate; it records caching as `PROVIDER_MANAGED_NOT_DISABLED`. API credentials do not replace its CLI login. Saved-result aggregation remains available after Evaluation finishes; see the [Analysis guide](../src/finarch/experiments/02-analysis/README.md).

Execution plans contain usage estimates; actual usage is recorded with the provider responses. Follow [Evaluation](../src/finarch/experiments/01-evaluation/README.md) and then [Analysis](../src/finarch/experiments/02-analysis/README.md).
