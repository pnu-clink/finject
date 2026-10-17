# Skimma file directory

The scheme is **The specifications for what kind of data type to include**So, input data and LLM responses use different criteria.

## Now check the file.

|Purpose|The file that changes the definition|Automatically generated JSON Schema|
|---|---|---|
|Full input is ready.|[prepared.py](prepared.py)|[01-preparation.01-source.prepared-input.schema.json](json/01-preparation.01-source.prepared-input.schema.json)|
|Enter to send to POT|[llm.py](llm.py)|[01-preparation.03-calculation.pot.request.schema.json](json/01-preparation.03-calculation.pot.request.schema.json)|
|POT grass answer|[llm.py](llm.py)|[01-preparation.03-calculation.pot.response.schema.json](json/01-preparation.03-calculation.pot.response.schema.json)|
|Reply to the question|[llm.py](llm.py)|[02-generation.02-generate-text.realization.response.schema.json](json/02-generation.02-generate-text.realization.response.schema.json)|
|Intent thank you reply draft|[llm.py](llm.py)|[shared.01-02.02-03.review-and-validation.response.schema.json](json/shared.01-02.02-03.review-and-validation.response.schema.json)|

`common.py`It prohibits additional fields and automatic type conversion. `registry.py`And then I manage the name, version, status and I create a JSON Schema. **[validation.py](validation.py)We read the same definition and run a real Python test.** JSON files are automatically generated copies for authentication and transmission, and not the second copy to be directly modified.](json/index.json)There's a version of each scheme, hash, and setup.

## How to Read Entries in a Schema

The schema files are in the **A term for a form**and **Entries that enter the actual data**So this is going to be together. `properties`It's a place to describe items, and it's a space in it. `facts`is the item that enters the actual POT answer.

|The term "skimma"|What do you mean?|How to read from this project|
|---|---|---|
|`properties`|It describes what items are in a JSON object.|The POT response is `code`, `facts`, `grounding`This is defined.|
|`required`|This is a list of the items that you need to enter.|If an item is missing from the list, it's rejected. `properties`Just because it's there doesn't mean it's necessary.|
|`type`|It's a data model of values.|`string`So, what is the sequence? `integer`is the integer, `boolean`It's true/false, `object`is a set of names and values, `array`It's a list.|
|`$defs`|It's a definition of a sub-structure that can be used in many places.|`Fact`The composition of the is defined here.|
|`$ref`|I'm referring to the structure defined elsewhere.|`#/$defs/Fact`This is the fact that the file is a fact.|
|`additionalProperties`|It determines whether you can get a name that you haven't already mentioned.|`false`Reject unknowns. The facts in POT response v2 are lists of fact objects with id, and each object receives only a specified field.|
|`enum` / `const`|This is a list of permissible values/one fixed value.|The correct answer type is an integer or float.|
|`anyOf` / `oneOf`|It's got to be one or more of the formats listed.|It's a string or null, different structures by source, etc.|
|`minLength` / `minItems`|Minimum string length/minimum list number.|It shows items that don't allow empty strings or empty lists.|
|`minimum` / `maximum`|It's the allowed range of numbers.|The precision is 0through 100at most.|
|`title` / `description`|It's a name and a description.|It's information for explanation, and the sentence itself is not a Python run test.|
|`$id` / `$schema`|This is the JSON Schema identification name for the scheme.|It's a different value than the problem ID of the run log.|

**It's different from having a null value and not having an item.** Current `scale`, `negative`The fact. `unit`It's a necessary item. `scale`and `unit`The value of the null is allowed but the item itself cannot be omitted.

## The contents of the ready input

[Push the button](json/01-preparation.01-source.prepared-input.schema.json) **List of problems**Each problem has all the following items, and the one that generates them is Python code that reads the source data.

|Item|What do you mean?|Current formatting and analysis|
|---|---|---|
|`id`|It's the problem number we use in this set.|It's not a blank string, it's not replicated in a bundle.|
|`raw_id`|It's the number that connects to the source problem.|It's not a blank string, it's not replicated in a bundle.|
|`context`|It's a text that's linked so you can read the original text and the table.|It's not empty.|
|`question`|It's a basic question.|It's not empty.|
|`source_content`|It's a structure of the scales and scales.|The tables are in the cells, the tables are the rows, the spaces are in the rows.|
|`context_mapping`|It connects which part of the text comes from which location of the text.|It checks in Python that each string in the block matches the actual context.|
|`reference_answer`|So we're going to put the source answer in a numbered string.|It's stored in a string and kept the numerical digits.|
|`reference_answer_type`|So this is the absolute-perfect division of the source equation.|An integer or float.|
|`reference_precision`|So this is the prime of the source answer.|0~100It's not the interpretation of the inverse of the question.|
|`answer_metadata`|It's a fair balance and an uncertainty.|The scale and the negative are essential.|
|`provenance`|Sources of data set, file version, and hashing.|FinanceReasoning is source_id/level, TAT-QA is document_id.|

`answer_metadata.scale`Silver is a string of allowances specified in the source. If there's no allowance, it's null. `negative`If the answer is true, it's false if it's not true.

### Primary location information

|Item|What do you mean?|
|---|---|
|`context_span`|It's the location of the text that starts and ends in context. 0Count from the beginning and not the end.|
|`source_pointer`|It's a path to find the bars or tabs in the source record.|
|`row` / `column`|It's the row number of the table space. 0is counted from the start.|
|`segments`|It's a list of links between the position of the text and the position of a text, by step or by section.|
|`numbers`|They're the number tags that you find in a string, which doesn't mean they're a validated financial basis.|
|`source_text_span`|It's the location of the numbers in the string.|
|`source_root`|It describes the source location path standard. The current value refers to the raw-record.json inside record of the runtime record. It doesn't mean that the problem-based files are back in the ready folder.|

### Enter the JSON text to the table

In paragraphs, tabs, and segments, you add an optional json_source, which may or may not be present in existing inputs. When the source_pointer is /context, the actual source is a string containing JSON, and it records its internal path separately.

|Item|What do you mean?|
|---|---|
|json_source.pointer|The path of the original context when you read the inside of a string in JSON.|
|json_source.source_span / raw_text|The text frames of the actual JSON tokens in the pre-conversion string and the original token tag|
|json_source.value_type|Key / string / integer / number / boolean / null|
|json_source.decoded_span|The area where the group title, the name of the action, etc. is shown in the decoded elemental token|
|json_source.markdown_escaped|Whether you've applied the table separator-switch-scape|

The context_span and the numeric position are the positions of the converted context. The JSON input converter compares the location and the free value of the raw token together and then performs this schema test.](../../../../docs/01-dataset/00-input/01-selection.md#json-%EB%B3%B8%EB%AC%B8-%ED%91%9C-%EB%B3%80%ED%99%98--in03j).

## What you send to the POT and what you get back.

POT is the stage of creating a grassroots program from the basics and questions. **It defines the input that you send and the response that you receive.**

### Send in the program request

|Item|What do you mean?|
|---|---|
|`context`, `question`|It's the original text and the question.|
|`reference.answer`|It's the source code that the author allows you to refer to.|
|`reference.answer_type`, `reference.precision`|So this is the type of the source and the prime numbers.|
|`provider_record`|It's a non-public source that the author allows, and the content varies from source to source, and it doesn't fix the internal key of the JSON object, and it's not sent to the independent response stage.|

### Answered by ProgramResponse

|Item|What do you mean?|Whether it's necessary or not.|
|---|---|---|
|`code`|It's the Python root code that I created.|Necessary, empty stringed.|
|`facts`|It's a list of numbers and base elements used in the array.|It's a minimum of one. Each item follows the Fact structure below.|
|`grounding`|This is a sentence that describes how these data are used in the array.|Necessary, empty stringed.|

**Fact one is a record of what source numbers the hammer brought in.** `facts`For example, an item that is a revenue is a sales base. It is converted to a search dictionary only after the response check is executed into an id, and the raw response list is kept intact. CLI rejected the dynamic key dictionary scheme and changed the response version to v2.

|The item in Fact|What do you mean?|The current format|
|---|---|---|
|`id`|It's the name of the base that you're looking for in the code as fact.|The empty string cannot be duplicated.|
|`span`|That's the beginning and end position in the context.|0 Two more integers. The correspondence test with the actual principle is the subsequent basis test.|
|`text`|It's a numeric tag that's taken from the original.|It's not empty.|
|`value`|It's a numerical expression that you use in calculations.|It's not a blank string. It's a test to see if the value matches the original.|
|`unit`|This is the place where we record the unit of this value.|It's not a blank string or null. The scheme doesn't know the meaning of the unit.|

`grounding`This means that the explanation has been submitted, not the judgment that the explanations are correct. `code`So just because it's filed in a string and it's passed the format validation, it's not even passed the run-and-response contrast.

## The response content of the other stages

### This is the first time I've seen this.

`patches`This is a list of what parts of the article you want to change to what sentences, and you need at least one.

|Item|What do you mean?|
|---|---|
|`start`, `end`|It's the correction of the beginning and end position of the original context.|
|`before`|It's a string before you change it.|
|`text`|It's a new string to be inserted. If you delete it, it can be an empty string.|
|`element_ids`|This is the number of elements in the graph that this correction represents.|

Python checks whether the beginning is behind the end, and in the actual application phase, it checks whether scope, element matches, overlaps, and changes actually.

### The answer is to answer the question.

Input: `context`, `question` So if you add the source correct answer and the output type, you're going to reject it in the input test. `text` We're going to have a natural language answer to one, and we're not going to require a specific label or a set of correct answers in response format.

### A pre-made drawing.

The three formats below are structural sketches that prevent the common call function from being used in actual model calls until the judging rules for each step are established.

|The drawing.|The main content|
|---|---|
|`InverseResponse`|Each item is variable_id, state, recoverable, undefinable, evidence, proposed, path, reason, etc. It's not a verified execution order that has a string of proposed paths.|
|`SourceResponse`|One source_annotation. Only the specified arguments contain side  A or B, text  source phrase, reason  Y. The Python call section checks that the specified side is the same as the side of the response.|
|`AuditResponse`|Each item is a criterion, a trial item, a judgment, a trial failure, a judgment not to be dismissed, a reason, evidence, or an audit opinion.|

### The scope of explanation and verification

The field name, type, or requirement is defined in the schema. The matching of the source metadata, the duplicate ID, the matching of text location, etc. is verified by additional checks on the same Python module. **Even if the LLM answers to the JSON Schema, it doesn't skip the Python test.**

## The schema verification file is validation.py

It's in the schema folder. **[validation.py](validation.py)**It's a common checking file, and input-ready code, step-run code, model response processing code uses this file.

|Function|What you get.|What we do and what we get out of it.|
|---|---|---|
|`parse_json`|JSON code|I read JSON, and the same item name comes up twice or if there's an invalid number, I reject it.|
|`parse_json_object`|The JSON response to LLM|Add to the above test and see if the top is the object.|
|`validate`|The name of the scheme and the data you read.|It checks the required entry, type, add entry, set Python conditions, and when it passes, it returns the input as it is, and fails, it causes an error.|
|`check_json`|The name of the schema and the JSON font|It returns the test results to PASS/FAIL, and if it fails, it lists the wrong item position and the reason.|
|Execute the command.|The name of the scheme and the file path.|The passing end code is the end code. 0Failure is a failure. 1.|

### A real example.

- first existing 10The input file passed the test.
- And then you copy that input only from memory, and then you get the first problem. `reference_precision` Calculate the value 0From string `"0"`The error location of the first problem is reference_precision and the reason is that it's not an integer.
- The independent answer. `text`Instead of a string, a number. 42If you put in, you're rejected. `text` You're going to be denied even if you don't have an item or add an item that's not in the definition.

The checker is a string. `"0"`The number 0It's the principle to preserve the raw response and leave the wrong field and reason behind.

## When do we deliver and test?

1. It brings in a response scheme that matches the role before the call. If it's not there, or it's empty, or it can't be created, then you don't record and call the FAIL.
2. It checks the model input. It allows only two entries, context and question, to enter independent answers.
3. When you call a model, it delivers the prompt and its response schema together. No request scheme is required to be sent to the model. The current request definition is to ensure that fields that are not allowed to enter are not mixed.
4. When you get the answer, you write the source code first, and then you test the JSON syntax and field type in Python.
5. The only response that passes is passed to the next procedure. The error is recorded with the raw response field position and not automatically corrected and recovered.

The common function of the call pre-post is [providers/structured.py](../providers/structured.py)The CLI connection code is added, but the internal tool block scan stops the actual model execution. The delivery method must specify native or prompt, and the actual support must be verified in the communication adapter. The CLI code uses the native response schema element. The common function only accepts the POT writing and independent response that the request format has been specified. The input projection of the phrasing request is still unconnected, and the detailed judgment agreement for the recovery, source, and response is unconventional, so it prevents the actual call to this common function.

`RunContext.invoke`The response scheme for the six LLM roles **Before calling the processing function** Check and talk. `response_schema` The Python processor functions list is separate, so it does not change to a schema deletion or a role name to an unscrew call. It does not re-record past functions that do not receive schema duplicates except for duplicates. If the step processing function returns the wrong answer to PASS, it stops as FAIL if it does not pass the field test. This is response format validation and does not mean that the verification is complete.

### The code verification results after the call

Model communication is `providers/structured.py`received a response scheme from the common boundaries of `transport(...)`And then I added the CLI code.](../providers/cli.py) `call()`We use this boundary to stop the actual process before it starts under the condition of internal tool blocking and checking. We apply the same response definition to the six LLM roles in the stages. We've separated the roles list so that even if the name disappears from the Schema list, the fact that it's an LLM role remains.

- Schema failure, bin definition, unknown role, transmission mode mismatch leaves a record of failures before calling.
- The step record is `03-result/schema-check.json`, `result.json`The problem is, `events.jsonl`In the same way, the common transmission function is called by the `03-result/schema-check.json`So let's leave the message on the left.
- If there's a raw response, we save it first and check the JSON syntax and the response field input. It doesn't automatically correct or re-code the error, and if the communication itself fails and the response fails, it doesn't record the failure and make a check pass.
- Delete the schema of six roles as a local variable while running the call function 0We've identified the routing, schema pre-storage, transmission, incorrect response retention, and cancellation, including the existing input, backup, and reverse checks. 39The items passed. It's not the actual model call result.

The local bandwidth of the draft role is used only for form-flow checks. The common transmission function blocks the actual communication of the draft-input injection unconnected role. Then, when you add the CLI connection, you have to use this boundary to make an internal star call, and you have to connect the schema transmission-response test together. That doesn't mean you've completed the check to the hidden request inside the CLI.

## Preservation and verification of input

It checks the location of the source code, the font, the cell, the source, the correct answer, the input, the digits, the alignment, the vowel symbols, and the corresponding position of the source, string, precision, and vowel flags in Python. It doesn't estimate the financial significance or the reverse direction of the question.

Existing 10·30·100The original input and hash are not rewritten. New schemas are applied when read. In the next set of new preparations, the schema name, version, hash is recorded in the manifest, and the incompatible version is rejected. The source pasting copy is a preservation material, and no LLM is used as a common input.

POT's code is a Python source string. The schema doesn't have a default output limit. The existing limit runner substitute is a separate POT execution, and it's not finished replacing this time.

## Use

Project-specific environment `.venv`In Pydantic 2.13.5I installed it and specified dependency on pyproject.toml.

```sh
PYTHONPATH=src .venv/bin/python -m finarch.dataset.schemas.registry --output src/finarch/dataset/schemas/json
PYTHONPATH=src .venv/bin/python -m finarch.dataset.schemas.validation --schema prepared.input --input data/prepared/first-10/input.json
PYTHONPATH=src .venv/bin/python -m unittest finarch.dataset.checks.test_schemas finarch.dataset.checks.test_preparation finarch.dataset.checks.test_pipeline -q
```

The method base: [Pydantic JSON Schema generated](https://docs.pydantic.dev/latest/concepts/json_schema/)[Extremely good type testing](https://docs.pydantic.dev/latest/concepts/strict_mode/)Fin-astra is read-only and doesn't copy the existing schema code.


## Sources plan scheme

`source_plan.py`is the original definition `json/02-generation.01-perturbation.ic-source-plan.schema.json`So this is the file that's going to get that definition. `SourcePlan.model_validate(..., strict=True)`It's not an LLM response scheme. 13It's a local production plan format.

- `base_plan_ref`, `base_plan_sha256`: Fixed A/B values; hash with the reference file of the calculation graph.
- `sources`A/B: A/B source ID, area, access to information, direct or indirect transmission, verification status.
- `intended_reliability`, `source_condition`: private production conditions and not exposed to the final text.
- `claim_order`: This family's fixed A/B sequence.
- `realization_rules`: two value preservation, source inheritance, correction and additional income pollution prevention, etc.
- `provenance`, `semantic_status`, `final_text_status`: specify that the source condition is made and that the meaning/subject test has not yet been completed.

For the creation of sentences `realization-input.json`In this case, the source code is the source code, the source, the source and the source code. `dtt.realize.response`Patches are formatted, and call and response verification is the next step in the wrong-way process.

The current source.plan only allows A_ONLY/B_ONLY, and the sources are exactly one, and the opposite source is dropped and not replaced with low reliability. The previous four candidate files are lead.

## 16Bar current connection

`llm.py::RealizationRequest`The C/Q Python code to be transmitted checks the structure and permission editing slots from within. This request scheme is not sent to LLM. `RealizationResponse` `patches` The scheme delivers it to the Codex CLI with a dedicated prompt, and after preserving the raw response, it validates it with the same definition. `program/dtt_realize.py::check_response`The actual record is now in the form of a "Skyma PASS" and not "PASS".16I'll take you there.](../../../reports/run/first-10-pot-validated-v3/test-0001/05-text/STAGE16-README.md)And then we follow.


## 17The meaning of the test response

`dtt.audit.response` V2 is the `findings` 8The following items are included: conservation, change, limitation, source, non-planned expression, civil law, correction, resolution, EA consistency: `observed_state`Quotations are a string of actual original/last text/question, and Python is contrasted. Item misses, duplicates, range errors, false quotations don't pass through. Semantic assessment is impossible and form error is not.

Internal `AuditRequest`The original, updated C/Q, change intent, edit list, and back-up checks. No request schemes are sent to the model. The response definition of past executions keeps the backup at that time.

## Step by step schema JSON file name

2026-09-15 Apply. `src/finarch/dataset/schemas/json/`The file name **Subsidiary steps. Operations. Request or reply.schema.json**And then we're going to do that. `index.json`It connects the registry schema ID to the actual file name. The internal ID, version, JSON content, hashing doesn't change the name just by changing it. `registry.py` `SCHEMA_FILES`I use it.

So the original review and the generated version verification use the same definition. `shared.01-02.02-03.review-and-validation`It's going to be shown as Preparation. `02-review-and-correct`, Generation `03-validation`I use it. `source.plan`The Python Local Planning Definition does not include any of the LLM responses in the registry.

| I.D. on the inside. | JSON file name |
|---|---|
| `preparation.revise.request` | `01-preparation.02-review-and-correct.revision.request.schema.json` |
| `preparation.revise.response` | `01-preparation.02-review-and-correct.revision.response.schema.json` |
| `preparation.evidence.request` | `01-preparation.03-calculation.review-answer-evidence.request.schema.json` |
| `preparation.evidence.response` | `01-preparation.03-calculation.review-answer-evidence.response.schema.json` |
| `dtt.feedback.request` | `02-generation.feedback.case-feedback.request.schema.json` |
| `dtt.feedback.response` | `02-generation.feedback.case-feedback.response.schema.json` |
| `prepared.input` | `01-preparation.01-source.prepared-input.schema.json` |
| `pot.author.request` | `01-preparation.03-calculation.pot.request.schema.json` |
| `pot.author.response` | `01-preparation.03-calculation.pot.response.schema.json` |
| `dtt.realize.response` | `02-generation.02-generate-text.realization.response.schema.json` |
| `dtt.realize.request` | `02-generation.02-generate-text.realization.request.schema.json` |
| `dtt.audit.request` | `shared.01-02.02-03.review-and-validation.request.schema.json` |
| `dtt.audit.response` | `shared.01-02.02-03.review-and-validation.response.schema.json` |
| `dtt.audit.response.v2` | `shared.01-02.02-03.review-and-validation.response.v2.schema.json` |
| `source.plan` (local planning) | `02-generation.01-perturbation.ic-source-plan.schema.json` |

Reading order: This correspondence table → schemas/README.md → json/index.json → corresponding JSON → Python directory. The current schema table of the Viewer shows the file path similar to this correspondence table and preserves the schema stored in past calls.

### Removal of misuse definition and location of public use

Currently, the draft of the draft of a reverse in the JSON and automatic export register, independent response request; response, and unresolved source phrase draft 4The schema response stored in past executions does not change. When you call the deleted role, the response is blocked before calling to the schema drop.

The public file name is `shared.01-02.02-03.review-and-validation.{request,response}.schema.json`.
- `01-02`: `01-preparation/02-review-and-correct`The original review and correction.
- `02-03`: `02-generation/03-validation`The proof of the generating gate.
- `response.v2`It's not for regular calls, because it's used in past response checks.

JSON now includes a local source plan. 15It's a items. 19It's the amount of time before the items is removed.

## Human-review Failure to interpret

`shared.01-07.02-05.failure-interpretation`and `shared.01-07.02-05.display-translation`The request/response JSON is `json/`The first is the English opinion linked to the evidence, the latter is the sign translation and the production verdict/feedback.

## QI05 Quality range sidecar

[quality_scope.py](quality_scope.py)It's dedicated to offline reporting and separated from the LLM request/response registry. `QualityReport.model_json_schema()`Lo [Real sidecar-schema.json](../../../../reports/run/20260916-quality-v1/sidecar-schema.json)It sends out the version enum.56 It checks the format-repeat ID-denominator, and the actual input is reconfirmed by the adapter. Independent review NOT_REVIEWED means that it didn't bring any review records from the selected base.

QI06 `response_screen.py`is for storage `response-screen-v2` The actual export is [review-v2/sidecar-schema.json](../../../../reports/run/20260916-review-v2/sidecar-schema.json)The report is in response_screen.json.](../../../../reports/run/20260916-review-v2/response_screen.json)It's separate from the LLM response schema.

QI02 `original_baseline.py`The public allowlist is a public-input-schema.json](../../../../reports/run/20260916-original-baseline-v1/public-input-schema.json)The private reporting contract is [sidecar-schema.json](../../../../reports/run/20260916-original-baseline-v1/sidecar-schema.json)The actual model request includes only public Q/C and not private reports.

QI03 `source_pair_review.py`The actual storage report contract is [source-pairs-v1/sidecar-schema.json](../../../../reports/run/20260916-source-pairs-v1/sidecar-schema.json)So this is [pair_manifest.json].](../../../../reports/run/20260916-source-pairs-v1/pair_manifest.json)Verify the accurate connection, the external reasoning, the external status and do not change the LLM response agreement.
