# EA reversal review record

Execution status: **{status}**Role: `{role}`.

In this call, only the question/text is transmitted after deletion. True/false is the inverse judgment of LLM, and both continue production. Call/response failure is not false. Python only verifies the response format, the location, the file connection, and does not solve the sentence or judge the meaning.

In order of reading:

1. `01-input/qc.json`: Actual review Q/C. `{observation_sha256}`.
2. `01-input/prompt.md`, `response-schema.json`: Guidelines and response agreement.
3. `02-call/`Request: raw response: usage: action log: response check: if some files are missing,
4. `03-result/inverse-review.json`: State and LLM Trial; Circumstances.
5. `03-result/evidence-display-check.json`Show coordinate checking. Only the quotation verifies the location and the raw response is preserved.

`01-input/private.ref.json`It's a production link record and it's not sent to the model. `latest.ref.json`Silver only shows the path of the latest original in the top folder.

Common `viewer/dataset`In this execution of the EA type **03-validation / 05-human-review**Selecting the base highlight and the formula, it distinguishes between the storage success and the screen check.
