# IC-RELATION replacement · concat · evaluation HTML preview checking

We didn't change the existing code or call the LLM, we checked the current copy and export code. **The substitution is possible, but the type selection execution alone does not automatically complete until the addition and export.** The following follow-up is planned to be included in the temporary relation scheduler and has not yet been implemented.

## Objects and current numbers

|Target|Current state of play|
|---|---|
|`20261003-001-CodeTAT-QA-0917-002`|288The following is the list of the countries of the European Union. 279, FAIL 9|
|CodeTAT-QA is a 7Type of full pass|260Case|
|Except for the IC-RELATION. 6Type of full pass|265Case|
|`20261003-concat-001` 7Type of full pass|1,260Article: Other sources 1,000 + CodeTAT-QA 260|

Another. 6If you keep the type, the concat pass cases can decrease and maximize the value of the new relationship. 1,265And the next passing case is `test-0256`, `test-0803`, `test-0883`, `test-0889`, `test-1455`It's not a prediction of success, it's a prediction that's different now. 6It's a limit calculated by type judgment.

## We found a connection issue and a processing plan.

|Current operation as verified|The follow-up process required by the temporary scheduler|
|---|---|
|Select the type to run. `selected-summary.json`I'm using the final `summary.json.latest`You're not going to be able to do that. `progress.json`, `result-report.json`, `results/`It doesn't update.|It reflects only the results of the new relationship in the final index and calls the existing report-fusion program. 6The result type and the environment maintain.|
|Selection execution ends before the verification fails the person review data storage stage. The final report requires the person review material even if it fails.|Existing `05-human-review.stage.run`Pass and fail both store data. This is not an approval process.|
|Concat is all `*-round`I'm going to copy the case folder, but the statistics are 1~3And the report is complete, Generation. 1~3I read the car.|It matches the progress and the latest index and index of the new regenerative variables. 1~3round records are not presented as new execution.|
|The concat program rejects the existing output folder and separates the source 8Replace the items-order and the whole record.|In the separate work folder, you'll configure and analyze the entire result, then back up and reflect the existing concat, and preserve the unchanged one's judgment of the existing concate.|
|The new HTML is a content hash that makes the distribution ID new, and the Import requires the distribution ID unit.|It preserves the existing HTML-assessment JSON, and when it's needed, it compares the existing and new content to the unchanged type, and maintains the previous evaluation, and the relationship between the changes is reassessed, and it doesn't necessarily transfer the ID.|

The re-interpretation of the temporary caller is the same as the previous generation `run_round`Using the feedback procedure, you need to pass on the previous case-by-case results. Simply re-coding the selected CLI to a new graph does not consider it to be passed on to the previous failed feedback. The spherical relationship placement plan is rewritten by the current placement version check.

## We must maintain export standards.

Preparation PASS and the latest 7All types are automatic PASS, and the original. In any type, only phrases without an explicit person Reject are included in the evaluation HTML. Accept is not required. If a new relationship fails, it will not replace the previous relationship with PASS. 7The type sort is then re-calculated to a new sentence. 6The type stays the same.

## The order of reading and the scope of verification

1. [validation.json](validation.json)The source: 3The hash of the items run, the hash of the file, 9A connection issue with a items local check.
2. [terminal.log](terminal.log): Check results and existing evaluation of HTML export return checks 5PASS.
3. [currently CodeTAT-QA data screen](http://127.0.0.1:8893/?run=20261003-001-CodeTAT-QA-0917-002).
4. [current concat data screen](http://127.0.0.1:8893/?run=20261003-concat-001).

I've verified the hash-ID alignment of the actual copy. 6Keep the type, different variables 7 PASS selection, the complete exclusion of one type of Reject, the missing progress index, the missing failed review data and the existing concat output rejection were reproduced. **The creation of a new LLM, the actual concat replacement, the browser import verification of the new final HTML has not yet been performed.** The existing dataset, annotation, HTML, has not changed.
