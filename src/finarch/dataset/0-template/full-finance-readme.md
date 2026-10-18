# FinanceReasoning full run for input

The source. {total}The clause excluded from the source selection criteria is {source_filtered}It's a blank text in the subject. {empty_context}That's the boolean right answer. {boolean_answer}That's the exact same transcript. {duplicate_qc}Except for the one. **{count}entries**The selection conditions and the existing number correspondence are recorded in selection-manifest.json. Not only is it blank, but it's also empty text, which is stored as JSON, empty arrays, passwords, and null. The source file hasn't changed. It's ready to enter for new Preparation, and the LLM verification isn't complete.

1. `preparation-result.json`: input generated; schema source hashing and results counted.
2. `selection-log.json`Excluded reasons, original ID, replacement ID.
3. `selection-manifest.json`: input/source hash, selection policy, new ID and raw_id correspondence.
4. `input.json`: ID → raw_id → Q → C → Run the correct answer metadata sequence.
5. `provider-records.json`The original file is not sent to POT.
6. `code-syntax-audit.json`The original: `python_solution`Python AST scan. There's an inter-type overlay and not a failure drill for the new POT.

Q and C both leave the first case in the same order of easy → medium → hard and the original file.

The Finance adapter converts the JSON object-type string array into a table if the actual context is empty, and the normal text is configured as it is. It stores the original data type and the numeric tag and source position in json_source. It does not determine whether or not JSON is the source ID alone. Provider-records.json stores the pre-conversion source code and records the PoT number position in the new context. This is an input structure check, not a root answer or meaning verification.
