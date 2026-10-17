# Local verification records of the experimental clearance work

[Report of the operation](../REPORT.md) → [post-completed verification](continuation-final-checks.json) → [Recent screenshot checks](continuation-final-viewer-checks.json) PASS is the passing of the file-code screen check at that point and does not mean the model response is correct or the user review is complete. 0And the actual experimental call is [the astronomical minister](../03-research/continuation-cost-ledger.json)It's in the past. 1Request and Success0is exp-004It's the API blocking power.

[Review of goodwill response](intent-review-checks.json)[Early documentation and surveillance inspection](../validation.json)[Early screen checks](../ui-review.json)It keeps the current execution and display results in the past, not the current executions.

|File|Role and scope identified|
|---|---|
|[dashboard-frame-checks.json](dashboard-frame-checks.json)|It's a common CSS with a top frame, color scheme, font panel, and a chart, chart, and price connection on both sides of the screen.|
|[dashboard-traffic-checks.json](dashboard-traffic-checks.json)|It's a tightly controlled screen in the form of JENNIFER, with real vision, full size, even scores, connection tabs, fees, and browser verification.|
|[dashboard-traffic-data.log](dashboard-traffic-data.log)|Actual start/finish time, timeline, wrong date, turnaround, end-of-day processing and existing 3,000I've verified the response. 17It's a items test.|
|[dashboard-traffic-routes.log](dashboard-traffic-routes.log)|And even on the controlled screen, you can check the server path to read only the registration asset and response ID. 4It's a items test.|
|[dashboard-traffic-explorer-checks.json](dashboard-traffic-explorer-checks.json)|Both factors contrast the axis, the complete visual alignment, the response corrector, the filter, the conservation of the endpoint, and the precision of the atmospheric calculation.|
|[dashboard-traffic-overview-checks.json](dashboard-traffic-overview-checks.json)|Completion of the division; condition-by-condition estimate;14The pair comparison, the ratio, the choice of connection, the conclusion, and the 0 The conservation of real 3,000Contrasting with the response. 12It's a items test.|
|[dashboard-checks.json](dashboard-checks.json)|The dashboard is the data collection on both screens, the choice of connection, and the actual browser check.|
|[dashboard-data.log](dashboard-data.log)|3,000Preservation of the response, null;0 I check the separation, the connection, and the read cache.|
|[dashboard-routes.log](dashboard-routes.log)|I check the server path and any file access level that reads only the registered screen and response.|
|[dashboard-overview-checks.json](dashboard-overview-checks.json)|The real answer is 30The condition set;14items P0/P1 comparison, cost, monitoring processing, reporting compared to links 8It's a items test.|
|[intent-review-checks.json](intent-review-checks.json)|7The original.20Connecting the response, the base file 33The hashing of the items, the new API call for this analysis 0It records the actual browser verification range.|
|[Reasoning for the response review](../03-research/intent-review-evidence.json)|It's analytics that links the rankings, the raw response, the questionnaire, the raw path, the status, the location of the employee, not the new correct answer, the new score.|
|[python-contract-checks.log](python-contract-checks.log)|V5 preservation, V6 expression rules, API adapters, and limited execution of 26items local return checks. The remote API processes the mouse.|
|[p1-classification-checks.json](p1-classification-checks.json)|The input judgment of current P1 verifies the input judgment; response method classification; P0 guidance output; common schema; past syntax definition preservation; no new model calls.|
|[p1-classification-checks.log](p1-classification-checks.log)|Offline return testing of the P1 classification agreement and the V6 OpenAI/Anthropic transmission adapter 16This is the items's final passing record.|
|[p1-classification-checks-initial.log](p1-classification-checks-initial.log)|The test code mistook the property sequence of the saved manifest for the transmission sequence of an initial failure record. `required` I modified it in order.|
|[prompt-layout-checks.json](prompt-layout-checks.json)|2026-09-26 The common section sequence, P1 sentence preservation, schema hash record at the time of the previous toxic editing.|
|[prompt-layout-checks.log](prompt-layout-checks.log)|V6 OpenAI/Anthropic Offline Returns Test at the time of editing 15It's a items passing record.|
|[viewer-contract-checks.log](viewer-contract-checks.log)|It's a viewer test that distinguishes between no numerical answer and a negative evaluation in a V4/V5/V6 set.|
|[documentation-checks.log](documentation-checks.log)|README template matching, progress sequencing, document coloring, local links, existing documents 79Check the items storage chart.|
|[prepared-run-checks.json](prepared-run-checks.json)|Definition of the run at the time of recording, input, visual hash and 3,000It's a past check that verifies the request. The number of current attempts follows status.json.|
|[research-contrast-checks.json](research-contrast-checks.json)|We leave the subset, bin object, answer field gaps as a comparison undervaluation, and we check that the existing correspondence tables are maintained.|
|[Reporting and verifying](../validation.json)|It's the result of a study of archives, reports, links, public documents, and a review of path restrictions.|
|[Certified Line Verification](../01-baseline/verification.json)|Existing input, raw response, result 12,008It's a preservation record of the items files.|
|[Number of responses returned by check](../01-baseline/missing-pair-regression-checks.json)|I'm going to make sure that the subset, the pasting failure, and the null mean are not the same.|

The replay command runs from the project root.

```sh
PYTHONPATH=src .venv/bin/python -m unittest finarch.dashboard.checks.test_dashboard_data finarch.dashboard.checks.test_dashboard_routes -v
PYTHONPATH=src .venv/bin/python -m unittest finarch.experiments.checks.test_experiment_contract_v5 finarch.experiments.checks.test_experiment_contract_v6 finarch.experiments.checks.test_experiment_openai_api finarch.experiments.checks.test_improvement_run
python3 src/finarch/documentation/manage.py refresh
python3 src/finarch/documentation/manage.py validate
PYTHONPATH=src .venv/bin/python -m finarch.experiments.02-analysis.legacy.comparison.improvement_report
```

Browser verification is performed directly from the existing public viewer by opening the report, experiment, entire picture, and stage listings. No separate HTML is created in the result folder. Model calls and limit policy verification are outside the scope of this local verification, and blocked calls are not marked as PASS.
