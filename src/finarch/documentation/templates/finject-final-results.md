# FInject PASS 1,354 The results of the experimental statements

The storage results are verified: __GENERATED_AT__The new Evaluation/Analysis model calls are 0entries.

## The range and reading order.

Final `data/final/finject-20261007`FinanceReasoning 1,071items and TAT-QA. 283And we're going to group the items into one FInject cohort. 7All the variations include human PASS, but the original, gold, answer, judgment, are not corrected.

The conditions on the chart are: `G⁺R⁺`, `G⁺R⁻`, `G⁻R⁺`, `G⁻R⁻`G is Guidance, R is Reasoning. `⁺`The ON, `⁻`is OFF.

1. `summary.json`: Model·G×R separate RQ1/RQ2/RQ3, review range, source run information.
2. `selection.csv`: final ID → source issue ID and file location.
3. `responses.jsonl`: Model; final ID; condition; variable by type save response results and latest A02 It preserves the existing run ID and response ID.
4. `manifest.json`The input hash, the latest attempt selected, the output hash and the verification results.
5. `execution.log`Local recruitment sequence and completed record.
6. `rq-results.xlsx`: Conditional comparison, quadratic, tripartite, original right/ wrong answer group and IC-source pair comparison.
7. `publication.json`: Location and hash of the local paper mark reflecting this statistic.
8. `verification.json`: final statistical contrast, Excel metric check, PDF compile and check the layout.

## denominator and unfinished

Case family 1,354Includes items x original 8inputs × 4items conditions = plan for model 43,328RQ1 and RQ2 are IC-v front/back, IC-r-ER front/back. 5And the items-like conditioning. 6,770RQ3 is two pairs of IC-v → IC-s and each condition is a pairing plan. 1,354entries.

The support rate is **And then we add up the drying.** The total is O=NS+AS/NS+NU+AS+AU, the number is N=NS/NS+Nu, the domain is A=AS/AS+Au. ND/AD is the judgement note, F is unreviewable and incomplete. These items are also in the plan denominator and the review range. 0It's N/A. NS/plans and AS/plans are also provided separately.

Gemini's R-OFF conditions were not in the existing runway plan, so `CONDITION_NOT_RUN`So, we're going to divide it into A0 of the stored R-ON response.2If it's not working, the support rate is uncertain.2 So it's not a case of proofreading, so it doesn't count as a failure of the root.

The original correct answer/response is consistency/disconformity with the existing numerical reference. Comparative inaccuracies are preserved as UNKNOWN. This is not the meaningful validity or independent answerable gold of the original description. NS/AS/NU/AU is also the LLM response basis judgment.

The answer to the existing experiments is on the viewer's comparison screen. **FInject final pass**Select the add-on value, and then check the raw response and judgement of each case in the source run. `paper/local-preview/rq*-table.tex`is the same `summary.json`I use it.

[Research results](http://127.0.0.1:8894/?run=20261003-exp-009-concat-002-luna&tab=answerable)[local paper PDF](../../../paper/local-preview/main.pdf)[Excel copy](rq-results.xlsx)You can open and check it out. `paper/local-preview/rq1-table.pdf`through `rq3-table.pdf`It's not transmitted to the Overleaf.

## Re-creation

```sh
PYTHONPATH=src .venv/bin/python -B -m finarch.experiments.02-analysis.01-results.final_cohort --output reports/analysis/<new snapshot folder>
```

Refuse to overwrite existing snapshots: source/final/frozen input, human PASS set, latest attempt, stop if the input hash is different. Actual model calls or source run set status changes are not performed.
