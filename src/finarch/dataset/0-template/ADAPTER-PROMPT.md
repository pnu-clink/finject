# Coding-agent prompt: implement the native three-stage adapter

Use this prompt when implementing manually. The automatic equivalent is
`make_adapter.py`, described in [README.md](README.md). Fill in the dataset
name and local raw paths, then give the block below to your coding agent.

```text
Implement the existing native input interface for a new source format in this
checkout. Dataset name: <lowercase Python identifier>. Raw paths, in order:
<one or more actual local files>. Source format notes: <known mapping or unknown>.

First read src/finarch/dataset/0-template/CONTRACT.md, template1_source.py,
template2_adapter.py, template3_schema.py and prompt1.md through prompt3.md.
Inspect the actual raw records and the existing helpers and validators. Explain
any essential ambiguity before implementing it. Do not guess missing fields.

Change exactly these code locations:
1. Create src/finarch/dataset/00-input/<dataset>.py from the fixed runner template.
2. Append one def <dataset>(record, question, source) to the existing
   src/finarch/dataset/00-input/adapters.py, callable as adapters.<dataset>(...).
3. Add <Dataset>Provenance and its union member in
   src/finarch/dataset/schemas/prepared.py.

Keep existing adapter functions, schema fields/validators, common helpers,
prompts, configuration and all downstream pipeline code unchanged. Keep every
prompt/template in 0-template; put only the generated implementation in 00-input.
If the existing helpers cannot represent the source, describe the exact blocker
before proposing any broader edit. Never weaken validation to force PASS.

Stage 1: implement iter_questions(document) and preprocess(record, question).
Preserve original records and exact raw pointers. Return ordered context_parts
and an unchanged question with a normalized displayed numeric answer. Use the
fixed displayed_number helper for explicit punctuation only. Preserve number
tokens, decimal precision, full relevant context and table structure. For FinQA,
qa.answer is the displayed gold; qa.exe_ans and source programs are not pipeline
answers or solutions. Do not solve, translate, round, rescale or infer meaning.
Validate complete record coverage, original pointers and the two normalized
adapter arguments against the source before proceeding.

Stage 2: use template2_adapter.py's fixed implementation; substitute only the
function name and dataset literal. Keep its signature, shared assemble and
extract_reference calls, and ten return fields exactly as defined in CONTRACT.md.
Do not move source-field loops, punctuation cleanup or location calculations into
this function. Check native fields, exact context spans, numeric tokens and
source mappings on every supplied record. Report the actual failing field paths.

Stage 3: use template3_schema.py for dataset, name and an actual 64-character
lowercase SHA-256. Add the class to the existing provenance union. Do not invent
source_id, level, document_id, URL or commit. The fixed runner adds id and
validates the existing eleven-field PreparedSample records.

Run the generated source runner with the raw paths and a new output directory.
Only intermediate.json and input.json belong in that data directory; source
records, manifests, status, exclusions and README belong under reports/run/.
Run the existing Finance/TAT-QA regression and a Preparation --plan-only check.
Verify unchanged raw file hashes and existing adapter functions. Verify the
installed code has no dependency on 0-template. Reconvert with the same installed
adapter into a second temporary output and compare deterministic outputs; use
actual raw files, not invented data. Keep extra checks outside data/.

Do not call live Preparation, Generation or Evaluation, install dependencies,
commit or push. Return the exact changed-file list and diff, mapping decisions,
real counts/exclusions, checks actually run, output locations and copyable next
commands. Distinguish structural checks from semantic or pipeline success.
```
