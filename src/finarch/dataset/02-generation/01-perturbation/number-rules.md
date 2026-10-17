# Python calculation before the number expression conversion

So, for example, the original value. `80,000`For the calculation `80000`The source code, the model raw response, the stored grass code, it's left.

The setting is [number-rules.json](number-rules.json)The execution code is [number_normalization.py](number_normalization.py)This is the current version. 2There's a thousand-unit comma removal of the computing value and a dollar sign adjustment of the original citation. `1,5`Commas that can have different meanings, like, are not removed arbitrarily, and the negative interpretation of the brackets or the unit translation is not included in this rule.

## Application order and adding methods

`rules` It's applied from top to bottom of the array, and the output of the front rule is the input of the next rule, and it doesn't end up being in line with one rule, but it goes through all the active rules. `enabled: false`The rules are broken.

|The registered processing method|Setup and operation|
|---|---|
|`regex_replace`|The whole value is `match` If you're in the regulars, `pattern` `replacement`R is the replacement.|
|`literal_replace`|The string. `from`The string `to`R is the replacement.|
|`strip_whitespace`|It removes the gaps at both ends of the string.|

The new pattern is unique. `id`, `kind`, `enabled`And we add the settings of the same method to the array, and if the process itself needs a new one, we can implement the Python function and then we can do that. `TRANSFORMS`The unregistered method is an error and does not run any code as setup. When the rules change, the version is updated, and the value is confirmed as an example of maintaining meaning and an example of rejecting.

A combination that ranks a string replacement → blank removal → regular replacement includes a test, and it doesn't automatically activate that combination as an operating rule.

## Record and failure.

By case `02-calculation/03-execute-python/02-number-normalization.json`The actual rules that are applied to the entire version of the hash, the base-by-base original values, the computation values, the variation rules, each rule is stored whether the input and output and variation of each rule are incorrect. `changed: false`Then we run Python, which must be passed by and contrasted with the source numbers, leaving the unprocessed comma tag as an error and stopping the execution.

The conversion tables and detailed inputs are checked in the Central Viewer's cache and correct answer tables. The stored code re-enactments are stored in the execution folder with the source hash without overwriting past failures.


## Original quote corrected by the editors 2

`source_rules`And it's applied in a registered way. `remove_adjacent_currency_prefix` method `align_adjacent_dollar_citation` The rule is activated: the specified range is a number, and in the original there's a real dollar right in front of that number, and if the difference between the model quotation and the letter within the range is only one dollar, it removes the dollar from the citation in the calculation copy, leaving the numeric value, the source value, the currency unit, and the biological code.

The order. **The proof of the citation as a proof of the original → the calculation of the numerical expression conversion → the proof of the correspondence of the original letters → the numerical value contrast → the Python execution**It's the same thing as the old python_runtime.py. 24Before you get to the second row, you're going to check if the value is different or if the currency is different or the location is different, and you're not going to cover it with this rule, you'll be recording the cause.

`number-normalization.json`In some cases `source_text`(Original quote) `validated_source_text`(Quotation for the investigation) `source_applied_rules`, `source_steps`The model does not overwrite the raw response or the stored program text.

## Operating principle: Autocomplete the number reading error

If an error is detected in the process of reading a number tag or converting it to Python numbers, the agent identifies the cause and adds and complements the rules. Without requiring the user to do so every time, they briefly inform the user of the problems they have found and the rules to add, then perform a correction, correction, and return check. If necessary, they register a new processing function and upload a rule version, leaving the original data and the conversion data, and verifying the results in README and Central Viewer.

It doesn't hide the numerical, unitary interpretation or gold inconsistency by stringing rules.
