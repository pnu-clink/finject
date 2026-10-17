# RQ1 Quadratic analysis data storage and inspection records

## Purpose and scope

2026-10-03 So, at the user's request, we can arrange the entire quadrant into an RQ1 analysis frame and then we can arrose the A0 of the docs.2 The model call, experiment run, property point, result viewer function implementation is not performed.

## File roles and reading order

1. [RQ1 analysis data](../../docs/02-experiments/02_analysis/02_comparison/01-rq1-pair-outcomes.md): purposes of analysis, quadratic; type; conditions, failures and denominators , null/classification, semantic assessment and viewer requirements.
2. [A02 README](../../docs/02-experiments/02_analysis/02_comparison/README.md), [Analysis README](../../docs/02-experiments/02_analysis/README.md): Read input to find new data. Created from the corresponding step template.
3. [events.jsonl](events.jsonl): Save-check execution and change document.
4. [validation.json](validation.json)This task: check the response of the link template, the color of the viewer document and the results of the entire document check.

This README is a template for](../../src/finarch/documentation/templates/rq1-pair-outcomes-log.md)It's generated from.

## Document viewer

[Read the RQ1 data from the public document viewer](http://127.0.0.1:8893/?run=20260927-experiment-documentation&doc=docs%2F02-experiments%2F02_analysis%2F02_comparison%2F01-rq1-pair-outcomes.md)Select the new data from the color of the existing document run. The result is not generating a folder-by-folder HTML.1/E02The quadratic function is recorded as a requirement only.

## Validation

`PYTHONPATH=src .venv/bin/python -B src/finarch/documentation/manage.py refresh`and `validate`ReadME text checks the color-link-guard chart. If there's an existing error in the entire test, it's separated from the verification results in this document and recorded in validation.json. The actual test results are read based on the file.
