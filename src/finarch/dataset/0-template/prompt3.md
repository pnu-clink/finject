Generate the exact provenance class declaration required by CONTRACT.md and
the supplied template. Return JSON with status="ready", reason, specification
and implementation. implementation is Python source, without Markdown fences.

Use the supplied class name and dataset name. Inherit StrictModel. Define only
dataset: Literal[dataset_name], name: Text, and
sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")].
Do not include imports or edit any existing class, union, field or validator.
The installer performs the single union addition at its known location. The
Python checker verifies your class against the fixed class contract.

The specification is {"dataset": supplied_name,
"required_fields": ["dataset", "name", "sha256"]}.
Actual source hashes have already been computed and checked in Python. Do not
request, count, invent or repair hash strings. No raw record or hash value is
needed for this stage. A Python PASS summary is supplied. On retry, correct the
class declaration; do not change the schema contract or its validation rules.
