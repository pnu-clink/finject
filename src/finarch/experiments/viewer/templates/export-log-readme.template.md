# Exporting data from the experimental viewer

`src/finarch/experiments/viewer/templates/export-log-readme.template.md`It's generated automatically.

1. [Browser checked](browser-checks.md): button; model; download file with unverified range.
2. [Exam results](verification.json): exp-001~005The actual request file number, sample detail contrast, input/request/result before SHA-256.
3. [local inspection](tests.log): {{export_tests}} Passage: check the online/offline equivalence, the source/link, the HTML insert string, the change, delete, take, and surround boundaries.
4. [Biotechnological log](build.log): The result of the compression progression and the transition.
5. [Real server logs](server.jsonl)Exit HTTP response and file size. Added when the server is running.

The verification view: {{export_verified_at}}. Run the experiment. LLM call is **0times**The original input and output files are written **0items**.

[List of HTML by page](../../outputs/experiment-exports/README.md) · [Blocker start and use](../../viewer/experiments/README.md) · [Responsibility chart and flow](../../docs/viewer-experiments.md)

The screen check to directly open the HTML file is blocked by the URL policy of the browser tool, which does not represent the contrast between download and data as user access completed.
