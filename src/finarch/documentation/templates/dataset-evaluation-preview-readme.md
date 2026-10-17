# Check the HTML for the evaluator

This README is generated from `src/finarch/documentation/templates/dataset-evaluation-preview-readme.md`.

1. [Use method: file responsibility: flow](../../docs/01-dataset/90-operations/04-viewer.md#%ED%8F%89%EA%B0%80%EC%9E%90%EC%9A%A9-html-%EB%82%B4%EB%B3%B4%EB%82%B4%EA%B8%B0)I read first.
2. [Authorized log](validation.json)Read the generated case, autocheck, browser verification range.
3. [Rating screen](evaluation-sample.html)It opens up. 20260917-002and 003Each of the test-0001·test-0002It's a four-case verification copy, not a full execution distribution.

|File|Role|
|---|---|
|`evaluation-sample.html`|A single HTML including the evaluation screen and the original view of the problem/type|
|`validation.json`|Actual data, automatic checks, browser verification scope and uncertain items|
|[workspace-checks.json](workspace-checks.json)|Problem/type movement, judgment, key, return to original and keyboard checks|
|[export-state-checks.log](export-state-checks.log)|File format: Import check: action separation: one case compression uncheck|
|[evaluation-screen.jpg](evaluation-screen.jpg)|The verification screen of the actual browser; the temporary validation displayed is the result of a data quality verification or the|

This screen provides a single screen for left type: problem tree and judgement bullet, original/variable statistics and value input, modified phrase/text context and calculation graph, bottom judgement analysis and keypad help. Filters for analysis, parameters guide and keyboard help are not displayed. The graph identifies the details from the whole text and the large view. The graphic uses the existing shape/example and does not add square cards, and is a combined A/B comparison with only stored variable transmission. Repeat the calculation or miss value 0It doesn't change.

The question is then shown as a large Q. **View original**The current problem-types are shown in the same HTML as the existing build-details. **Return to evaluation**It's back to the original evaluation item. It keeps the key and the judgement, and in the original view, it doesn't modify the judgement. It doesn't require any server-external files.

The name of the evaluator → Number Pad 1 Pass through. 2 Failure. 3 You can automatically use the following sub-valuation move → Temporary storage or result Export sequence. If you turn off the check, it keeps the current item. ←/→ moves to the current determination/browse filter, and you can modify the previous determination from the entire filter. Enter the key to N. Enter is the key to save and enter termination, Shift+Enter is the column. Key is optional. Browser temporary recording and JSON are taken from Import. The original creation determination is not changed.

**Q/E**The problem before/after the judgment filter is the correct scan, **A/D**is the same type of problem before/after. **v / Shift+V**The current filter is moved to the next/previously saved Ubo Error item in the search. The move is also active in the original view and excluded during the input. The graph is fully customized when first displayed and the window size changed.

The actual distribution is the [Public Production Viewer].](../../viewer/dataset/index.html) **Export reviewer HTML**In this example, you can select the execution and tag cases and generate them. `I'm not going to be able to do this.`The validation judgments and screen captures in this folder are not the actual data quality evaluation results, no LLM calls and no production data changes.
