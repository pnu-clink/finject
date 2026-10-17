# The independent ranking behind the table

The creation and verification prompt v4 added a prohibition on inserting phrases inside a table. The Python plan specifies a coordinate after the last row of the entire target table, requiring a blank line.

## Read order and verification range

1. `validation.json`: Results of the examination and summary of the change of position.
2. `terminal.log`Related: 31items local inspection.
3. `test-0100-placement.json`, `test-0105-placement.json`Python placement verification that reuses stored English phrases and is not the result of new LLM creation or meaning verification. The existing run, updated copy, evaluation, HTML Import ID has not changed.
4. Preview below: You can read it from the document view of the common dataset viewer.

The standard legacy prompt test did not pass past fixture failures and current inconsistencies with the Model-General Directions-EA statements. The error does not include the basis for passing this change.

{{EXAMPLES}}
