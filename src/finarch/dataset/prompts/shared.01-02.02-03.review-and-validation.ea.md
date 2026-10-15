AUDIT TYPE: EA — TARGET INPUT ABSENT, REMAINING TEXT COHERENT

planned_change
Identify the observed input from intent.target and intent.deletion. Check final
context AND question, including direct restatements, number words and equivalent
unit expressions: a target still supplied by the question is not absent.
The same digits for another quantity, entity or period are not the target; retain
them. Preserve its financial category and all other inputs/conditions consistently
with the original. Check absence of this observation, not impossibility of every
answer. A separate Q/C-only call records inverse recoverability for analysis.
Recoverability does not invalidate the deletion and must not cause FAIL/UNKNOWN.
Do not perform that inverse review using the original context in this audit.

unintended_change
Use intent.authorized_edit_slots. Within the authorized sentence, allow removal
of amount-introducing words and grammar repairs; require neither character-only
deletion nor incomplete clauses. Reject changes to other values, conditions or
question meaning, invented numbers/facts, zero/guess substitutions, deletion
notices, missing-information explanations, construction tags or answer hints.
For an authorized fixed table cell, preserve table structure and other cells.

readability
Read the sentence with its neighbors. Reject bare currency symbols, orphaned units,
unfinished predicates, "The loan amount is $.", or "The bank offers a loan with a term."
Deleting target characters does not excuse malformed prose. An authorized empty
numeric TABLE CELL may stay empty if its row/column identify its meaning; it need
not form a sentence. Intended absence, harmless list punctuation, formatting or
tense alone are not readability failures.
