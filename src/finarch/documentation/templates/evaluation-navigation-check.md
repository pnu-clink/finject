# HTML evaluation · filter based move verification

## Changes

- `Q/E`It's only going to the previous/next problem that matches the judgment filter and the problem number search. It keeps the current type of the problem matching, or it opens the first type that matches.
- ←/→ Only move the previous/next items that match the filter search like buttons and keys.
- `v`The following saved ubo failures, `V` Or `Shift+V`The default is to move to the previously stored Ubo. It maintains the current filter and search and troubleshooting/type mode.
- It doesn't move between the input window, the converter, the IME combination, it stays at the end, and it doesn't cycle for the first time.
- `A/D`The same problem in type moves and automatic judgment and reservation rules keep.

`viewer/dataset/evaluation/workspace.js` `evaluationFilteredEntries`Share the list: issue moving; traffic moving; e-mail/failure moving. `assets.py`So we reassembled the common screen and then we re-evaluated it and then we expanded it into the HTML Export.

## Reading order

1. `validation.json`Fixed actual download HTML path, hash before change, deployment ID; internal data preservation checks and browser verification or not.
2. `terminal.log`Automatic checking results from HTML changes.
3. `workspace-checks.json`Moving, access protection, and judgment preservation 13items are back.
4. `original-html/`: Independent backup of HTML before change.

The evaluation screen is the downloads of the existing `20261003-003- The evaluation.`, `20261003-concat-002- The rating.1).html`, `20261003-concat-002- The evaluation.`Newly open or re-encrypt. The phrase compression data, distribution ID, evaluation JSON format is maintained so that you can use the existing import and evaluator-specific browser temporary records.

```shell
node src/finarch/dataset/checks/test_evaluation_workspace.cjs
# Filter scan, v/V, input protection and judgment and key preservation.
```

The security policy of the browser tool is `file://` The browser performance test of the actual download HTML was not performed by declining the header. It was not circumvented and the automatic check pass is not considered as a completed browser verification. There are no LLM calls and production-evaluation judgement changes.
