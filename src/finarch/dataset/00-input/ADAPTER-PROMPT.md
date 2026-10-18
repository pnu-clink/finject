# Create an adapter with a coding agent

Open your local FInject repository in a coding agent such as Codex. Supply the
raw file paths and a dataset name, then paste the prompt below. The agent authors
Python code; running the completed adapter must not call a model. Start after
following the installation instructions in the repository README.

For the full workflow and commands, see [Write an adapter](ADAPTER.md).

## Prompt

Create a deterministic source adapter for this FInject checkout.

My dataset name: `<dataset name>`
My input files, in order: `<one or more local paths>`
Known field mapping or source-format documentation: `<describe it, or write unknown>`

Read `src/finarch/dataset/00-input/ADAPTER.md`, `adapter_template.py` in that
directory, and `src/finarch/dataset/shared/adapter.py` before writing code.
Inspect the actual input structures and several actual records. Do not invent
sample data or assume a field mapping from its name alone. If the question,
context, gold answer, file-join key or numeric notation is ambiguous, ask me for
the minimum missing information before implementing that part.

Create only `src/finarch/dataset/00-input/adapter_<dataset_slug>.py`, using a
lowercase identifier for the slug. Never overwrite an existing adapter. Do not
edit the template, core pipeline, schemas, prompts, settings, existing datasets
or any files outside this checkout. Derived verification outputs may be written
to new directories under `data/prepared/`. No commit or push is requested.

Implement `adapt(sources)`, following the supplied template. `sources` is an
ordered tuple of `RawSource` objects. Use `source.json()` to read JSON while
preserving decimal tokens. For CSV/JSONL or another text format, parse
`source.text()` deterministically and preserve answer tokens as strings. Never
parse gold with `float()`. Use `make_record(q=..., c=..., a=..., origins=...)`;
the helper derives `a_type` and `a_precision`. Its numeric-string parser accepts
only an unambiguous JSON number. Any additional numeric-format rule must be
justified by the actual source format and documented in the adapter.

The intermediate has exactly `q`, `c`, `a`, `a_precision`, `a_type`. No scale,
difficulty, solution program, source-family label or inferred semantic metadata
belongs in it. Preserve original question wording and answer value/precision.
Do not solve, translate, round, rescale, infer units, rewrite a question to match
gold, execute source solution programs, or call an LLM/API/network service.

Assemble the context mechanically. Preserve relevant headings, row/column labels,
paragraph order, units, captions and footnotes. Do not insert gold or solution
annotations into the context. For multiple files, join only on documented keys;
reject missing or ambiguous joins. Preserve every contributing source record
using `source.origin(record, locator=..., index=...)`; `index` is optional and
must be the actual top-level array index when supplied. Use exact JSON pointers
or clear row locators. Include a question-specific locator when a document has
multiple questions. These origins are bookkeeping, separate from the five-field
intermediate; the common builder generates IDs, hashes and manifests.

Yield `exclude(reason, origins=...)` for explicitly unsupported question kinds,
with a concrete reason. Do not silently skip malformed numeric questions or
drop distinct questions that share a context. Retain deterministic file and
record order. A conversion error must be visible, not replaced with guessed data.

After writing the adapter, run `python -B -m finarch.cli prepare-custom` with
`--adapter`, one `--input` per source file, `--name`, and a new `--output` directory,
using the repository virtual environment and `PYTHONPATH=src`. Run it twice into
different new directories and compare `intermediate.json` and `input.json`
byte-for-byte. Confirm raw file hashes did not change. Inspect actual Q/C/A and
precision against representative originals, including tables or joins when
present. Report explicit exclusions and any unsupported cases.

Validate with schema `01-preparation.01-source.custom-input`, then run the
existing Preparation scheduler with `--plan-only` on the produced `input.json`.
Do not start live Preparation, Generation, Evaluation or model-assisted Analysis.
Do not install dependencies, alter the core pipeline or weaken validation to make
a failing conversion pass; report the exact blocker instead.

Return the adapter path, concise field/context/join rules, counts and exclusions,
the checks actually performed, exact copyable conversion and plan-only commands,
and the output locations. Distinguish format validation from semantic correctness.
