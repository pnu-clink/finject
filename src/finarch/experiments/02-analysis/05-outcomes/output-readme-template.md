# {{run}} / Results of the response

In order of reading: `summary.md` → `summary.json` → `responses.jsonl`.

- `summary.md`: Model by Model / Prompt by Model / Reasoning by Model 5
- `summary.json`The original. 7The items variant / H1 5The denominator of the differential variation, the differential property, the input hash and the output hash.
- `responses.jsonl`All scheduled responses: `semantic_answerability`The NASU is a type A02 Reason and citation, accurate response ID.
- `history/`The derivative before the resization. The synthesis input and the model raw response do not change.
- The run dynamics are the top run. `events.jsonl`and `pipeline.log`in `SEMANTIC_RESPONSE_OUTCOMES_CLASSIFIED`It's written in R.

`semantic_answerability`And the result of this derivation is **The answer is:**It means.
`SUPPORTED_ANSWER` / `SUPPORTED_ABSTENTION` / `UNNECESSARY_ABSTENTION` / `MISSED_ABSTENTION` / `UNCLASSIFIED`I use it.
The state of the case is not clear. `item_answerability`The NS/AS case status estimate is not independent Gold.

NU/AU alone does not confirm unnecessary authority or failure of authority, and even inconsistencies in the original answer do not guarantee the impossibility of a case.
Without an explicit independent review of the clause, the case remains in a subdivision with the specifics.
The original response is now A0.2So it's not a subject of proofreading, so it doesn't change the original number of correct answers to a valid answer.

The existing experiments viewer's Analysis → Basis validity screen checks the five classification tables of the same execution.
No additional model calls.
