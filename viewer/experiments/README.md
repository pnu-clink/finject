# Experiment viewer: Evaluation and Analysis

This viewer reads `reports/experiments-run/`. It does not submit Evaluation or Analysis requests. Complete the [installation](../../README.md#installation-and-credentials), including Node.js, and follow the [Evaluation runbook](../../src/finarch/experiments/01-evaluation/README.md).

## Offline example without API keys

From the repository root:

```sh
PYTHONPATH=src .venv/bin/python -B -m finarch.experiments.pipeline prepare \
  --config config/experiments/reviewer-smoke.toml
PYTHONPATH=src .venv/bin/python -B -m finarch.experiments.viewer.server --open
```

Open http://127.0.0.1:8894/?lang=en and select the run printed by prepare in **Run records**. Each prepare creates a new experiment folder; select the intended one. The sample prepares one family, eight original/variant inputs, and 32 requests. It has no saved target-model answer, billed usage, or completed Analysis.

On macOS, `viewer/experiments/start.command` launches the same server. Stop it with Ctrl+C. An alternative `--port 18894` changes its address. For a separately stored real experiment collection, `--root PATH` sets the experiment-run parent directory; it is not an individual run folder.

## Read the screens

1. **00 Input / Inputs and delivery** shows the selected dataset, public/private split, frozen prompts/schema, per-model request manifests, and saved output paths. Private reference material is kept outside the solving model's input.
2. **01 Evaluation / Overview** shows request composition and collected/failed/uncollected counts. In the offline example, 32 requests remain uncollected; zero collected responses is not a 0% accuracy result.
3. Select **Browse cases → id-0001** (or search another saved case), then **Case comparison**. Choose type `00 Original` or a type `01–07`, a prompt condition, and Reasoning OFF/ON. **Input sent to the model** exposes actual Q/C, prompt, JSON schema, and additional fields. The sample original asks for intangible-asset amortization across 2018, 2017, and 2016.
4. **Responses by model** shows the actual saved response and state. In a prepared-only run it says **Not run** / **No response**. **Exact request**, checks/diagnostics, attempts/usage, **Cost and execution**, and **Failure analysis** expose the corresponding saved evidence when available.
5. After finished Evaluation and successful [Analysis](../../src/finarch/experiments/02-analysis/README.md), select **02 Analysis** and its result/comparison/research views. Follow observations/findings back to original case/item/response references and their evidence. Check assessment coverage, failure/non-reviewable rows, and source hashes before interpreting conclusions. The separate **03 Quadrant** view needs its actual saved outcomes/findings; a prepared run cannot populate them.

Use the model, experiment, type, solving-condition, reasoning, response-status, and case-search controls to make comparisons under matching conditions. Format validity, original numeric match, declared classification, semantic answerability, and response grounding are separate. Empty assessments and unfinished stages stay unevaluated.

Choose English in the display controls. Source Q/C and model responses retain their saved text.

Browser assets are here; the Node server and artifact readers are in `src/finarch/experiments/viewer/`. The optional [widget](../../apps/README.md) starts the server but does not create an experiment or configure authentication.
