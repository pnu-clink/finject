# Generated dataset input

Source: `{source}`. Input preparation reads the manifest and `dataset.jsonl` without opening the construction run. Selection: {originals} originals and {variants} variants. These files are prepared before API execution.

Read:

1. `selection.json`: selected/excluded records and reasons, dataset hashes, annotation policy, and missing Analysis metadata.
2. `public.jsonl`: item ID, question, context, and decimal precision. Target-model requests omit the item ID from solving input.
3. `private.jsonl`: references, production decisions, annotation, edit history, and original/variant relationships. This material is not sent to the solving model.

Analysis metadata status: **{analysis_status}**; recorded gaps: {gaps}. Missing information is not inferred or treated as Analysis readiness. Pending decisions are not Accept. Separate annotation requires an explicit selection policy before preparation.

Inspect the actual files in the experiment viewer's Input and case screens.

## Usage

From the repository root, run `PYTHONPATH=src .venv/bin/python -u -B -m finarch.experiments.pipeline prepare --config config/experiments/config.toml` after setting `generated_path`. It prepares public/private inputs and requests without model calls. To resume the same experiment, use the run README's `run --evaluation-only --run` command instead of preparing another run.

Selection/exclusion reasons and missing metadata are recorded in `selection.json`. Construction decisions, references, and annotation remain outside the target-model public input.
