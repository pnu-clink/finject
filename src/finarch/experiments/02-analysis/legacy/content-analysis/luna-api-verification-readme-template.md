# {run_id} Verification of the API records

The verification view: {checked_at}The result: **{status}**In this verification, the additional model calls are 0entries.

1. [Summary of the action](../RUN-SUMMARY.md): Complete sum; cost; source number comparison; response equivalence.
2. [verification.json](verification.json): {requests}The original API usage of the request and the result of the verification of the cache control, model, response status.
3. [raw-hashes.json](raw-hashes.json)Try: real transfer of JSON and raw response files to SHA-256.
4. [test-0006.json](test-0006.json): API off/on response and usage of the user-indicated case.
5. [identical-original-example.json](identical-original-example.json): Cache reading and writing 0In the same JSON as the whole source items response pair.
6. [events.jsonl](../events.jsonl)The following are the steps: preparation, exit, completion of the application, analysis, verification of the documentation.

Reproduce command: `PYTHONPATH=src .venv/bin/python -m finarch.experiments.02-analysis.legacy.content-analysis.luna_api_review --run reports/experiments-run/{run_id}`Readme is the only way to read the results. `src/finarch/experiments/02-analysis/legacy/content-analysis/luna-api-verification-readme-template.md`It's generated in the Star, and it doesn't create any HTML, and it checks the source in the Markdown panel and the experimental viewfinder.
