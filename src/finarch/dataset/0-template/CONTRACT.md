# Adapter input and output contract

This contract preserves the existing `00-input/adapters.py` return fields and
`schemas/prepared.py::PreparedSample`. It does not introduce a replacement
input format. `question`, `context`, `reference_answer` and
`reference_precision` are the field names, not `q`, `c`, `a` or `a-precision`.

## 1. Source file: raw files to original records

Generated file: `00-input/<dataset>.py`.

Public function: `read_records(paths) -> dict`, where `paths` is a nonempty
list of local JSON, JSONL or CSV paths with the same source layout. One file
may contain several questions; several files may each contain one or more.

The model implements two functions in the source file:

| Function | Input | Output and responsibility |
| --- | --- | --- |
| `iter_questions(document)` | A list of unchanged original records. | Yield each original `record`, its original `question`, their pointers and an `included` flag. No source rewriting. |
| `preprocess(record, question)` | One original record and selected question. | Select ordered context pieces and the displayed answer; normalize literal answer punctuation. Return the two adapter inputs below. |

The source file uses the fixed `displayed_number()` helper to remove declared
literal punctuation. It returns a JSON numeric token string: `"14%"` becomes
`"14"`, `"9.9%"` becomes `"9.9"`, and `"1.00"` keeps both decimal places.
No scaling, solving, semantic rounding inference or use of `qa.exe_ans` occurs.
The model writes actual source field reads and loops, not a mapping interpreter.

The normalized inputs are internal Python dictionaries, not a new input.json
schema. For FinQA, `preprocess` returns:

```python
(
    {"context_parts": [
        {"kind": "text", "source_pointer": "/pre_text/0", "value": original_text},
        {"kind": "table", "source_pointer": "/table", "value": original_table},
        {"kind": "text", "source_pointer": "/post_text/0", "value": original_text},
    ]},
    {"question": original_question_text, "answer": "14"},
)
```

All text fragments are included in their original order; the example only
illustrates the structure. `value` equals the original scalar or matrix, and
`source_pointer` points inside the unchanged raw record. The preprocessor does
not construct final context text, spans, number locations or mapping IDs.

The fixed reader computes file hashes and a stable `raw-<24 hex>` ID. It adds
that ID as `uid` to the adapter question. Each returned reader row retains
`record`, `question`, `source`, `record_pointer`, `question_pointer`, `raw_id`,
`record_index`, `source_metadata`, and additionally `adapter_record` and
`adapter_question`. `sources` and explicit `exclusions` retain their roles.
Original records remain untouched in provenance evidence.

Stage 1 declares `records_path`, `questions_path`, `include` and `fields`.
`fields` identifies question/answer paths, ordered context paths/kinds and
literal `answer_format`. Text paths select scalars (`/pre_text/*`); table paths
select matrices (`/table`). Python checks every original record and both
preprocessed arguments against this declaration before stage 1 passes.

## 2. Adapter: checked inputs to native sample fields

Public callable: `adapters.<dataset>(record, question, source)`, using the
existing TAT-QA positional argument pattern. All newly generated adapters have
the same argument fields and the same fixed implementation:

| Argument | Required content |
| --- | --- |
| `record` | `context_parts`: ordered text/table pieces with original pointers and values. |
| `question` | `uid`, unchanged `question` text and normalized `answer` token string. |
| `source` | Actual file `name` and `sha256`. |

The function is appended to existing `00-input/adapters.py` and uses the same
module-level helpers as Finance/TAT-QA: `assemble`, `extract_reference` and
`Decimal`. The complete implementation is in [template2_adapter.py](template2_adapter.py).
Only the function name and provenance dataset literal vary by dataset.
The checker rejects changes to the implementation, signature or shared calls.

- `assemble(record, "parts")` in existing `00-input/content.py` constructs
  context text, original paragraph/cell locations and lexical number spans.
- `extract_reference(load_raw(question["answer"]))` registers the numeric
  token using the existing common reference helper. A fixed `-0` case preserves
  integer negative zero without changing that helper or other datasets.
- The adapter returns native fields and provenance. It contains no raw-field
  selection, punctuation cleanup, context loops or coordinate calculations.

The return has exactly these **10 fields**; the runner adds `id`:

| Field | Meaning |
| --- | --- |
| `raw_id` | Checked `question.uid`. |
| `question` | Original question text from the preprocessor. |
| `context` | Original fragments assembled in declared order. |
| `source_content` | Original paragraphs and tables with exact locations. |
| `context_mapping` | Segments and lexical number locations. |
| `reference_answer` | Registered displayed numeric answer. |
| `reference_answer_type` | Integer/float token notation, not an inferred instruction. |
| `reference_precision` | Displayed decimal precision. |
| `answer_metadata` | `scale=null` and the numeric sign. |
| `provenance` | Dataset name and actual source-file metadata. |

Shared `content.py` owns paragraph IDs (`paragraph-0`, ...), table/cell IDs
(`table-0-cell-0-0`, ...), Unicode half-open spans and the fixed number_status
`lexical candidates only; meaning and units not validated`. New adapters do not
reimplement these rules. Its parts path uses two newlines between fragments,
newlines between table rows and ` | ` between cells; empty cells keep locations.
The preexisting Finance and TAT-QA assembly paths and functions are preserved.

Stage 2 copies `fields` from stage 1 as its validation specification. It cannot
change already-checked source bindings. Failures retain the original reason;
field mismatches include JSON Pointer `path`, `actual` and `expected` values for
repair. Existing raw-only reader responses use an older contract and cannot be
resumed into this preprocessed-input interface.

## 3. Schema registration and input.json

Generated addition to `schemas/prepared.py`:

```python
class <Dataset>Provenance(StrictModel):
    dataset: Literal["<dataset>"]
    name: Text
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
```

The installer adds this class to `PreparedSample.provenance`'s existing
discriminated union. Existing classes, common fields and validators are
preserved. `source_id`, `level`, `document_id`, `url` and `commit` are not
invented for local files. Existing Finance/TAT-QA definitions retain their
original source-specific fields.

Schema validation checks data; it does not construct or rename it. The runner
adds `id="test-0001"`, `id="test-0002"`, etc. to the adapter dictionaries,
validates the **11-field** records, and writes their JSON array to `input.json`.
This is the existing `01-preparation.01-source.prepared-input` schema. The
unchanged native loader and Preparation scheduler must accept it before PASS.

`intermediate.json` is only a four-field inspection projection of these same
records: `question`, `context`, `reference_answer`, `reference_precision`.
It is not a separate input schema or an alternative processing route.
Only these two JSON files are written to the data output directory. Original
record copies, validation status, hashes, exclusions and README belong under
`reports/run/<run>/00-input/`; authoring requests and checks belong under
`reports/run/<run>/adapter-generation/`.

Adding a provenance union member changes the schema fingerprint. Existing
prepared manifests are preserved; they may need rebuilding for the new schema
fingerprint. No downstream pipeline code or validation rule is changed.
