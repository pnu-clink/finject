# LLM call change comparison

1. REQUEST-CHANGE-REPORT.md: Prompt, input, schema, response difference and selected attachment record.
2. request-change-report.json: Data that shows the same data in the shared viewer. before/after.path is the actual call step folder.
3. request-change-events.jsonl: output storage power according to the action log structure.

The previous and later LLM step folders are specified as --before, --after. Read the actual transfer records of each folder and do not call the new model. --validation, --local-repair is an optional add-on.

In Preparation, the comparison JSON is identified by the pre-LLM request change button in the case. The automatic placement generating connection is a constellation, and this function itself compares the two specified calls.
