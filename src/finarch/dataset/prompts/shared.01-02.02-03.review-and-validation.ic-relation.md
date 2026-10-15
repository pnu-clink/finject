AUDIT TYPE: IC-RELATION — SOURCE-GROUNDED RELATION CONFLICT

planned_change
Require the planned relation, operand identities, direction, coefficient, each
operand's entity/period/unit and aggregation scope. Preserve original numeric
observations and verify a genuine conflict with them. Matching the plan, a saved
PASS or a changed computed answer alone is insufficient.

Planned cross-period comparisons are allowed: evaluate each operand in its own
period. Different quantities are also allowed. Do not reject either merely for
being different, or invent an unplanned entity, period or financial assumption.

For a total-component relation, require the total on the left. Reject a relation
that makes a nonnegative component exceed its containing total in the same
entity, period and unit, including when a cross-period reference causes that
violation. If Q/C cannot establish a claimed part-total relationship, mark
planned_change UNKNOWN and identify the missing evidence. Prefer another period
in planning, but do not fail an otherwise valid relation solely for using the
same period. Check the conflict; require no extra computed-answer set.

unintended_change
The added sentence must identify the left target by quantity and period only.
Reject repetition of its observed amount, such as "the 2015 balance, $1,136,
was twice ...". That amount must remain unchanged in the original context.
The right reference amount is permitted only by the edit slot. Equal numeric
values on both sides do not prove a violation; check which quantity is stated.

Reject replacement of original observations, evaluated replacement amounts,
extra/reversed relations, unplanned numbers, period/unit shifts, source claims,
answer hints, construction tags and corrections resolving the intended conflict.
Preserve the question, calculation method and unrelated evidence.

readability
If the target is in a table, require the added relation after the entire table
as a separate paragraph with a blank line. Reject prose appended to a table row
or cell, or inserted between rows. Preserve the original table structure.
Require one natural, unambiguous factual relation with clear quantities and
periods: X is twice Y and Y is twice X are not interchangeable. Do not treat
intended conflict, harmless formatting or tense alone as unreadability.
