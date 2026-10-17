# Experiment-result HTML files by run

This list is generated from `src/finarch/experiments/viewer/templates/export-files-readme.template.md` and saved verification records.

Each file contains **one complete run**. Open it in a browser to search, filter, switch tabs, and compare cases. No separate server or data folder is required. Analyst-only original reference answers are included. Later experiment changes are not reflected in an existing export.

| Run | Requests | Cases | HTML size | Files over the source limit |
| --- | ---: | ---: | ---: | ---: |
{{export_file_rows}}

**Reading order:** condition comparison → case selection → raw responses/requests → reports/history. These copies start in the condition-comparison view. Open another run's HTML to inspect that run.

Files larger than 8 MB show the same exclusion message as the online viewer; this includes `label-migration/originals.zip` in exp-001/002. Displayed case inputs, responses, raw records, and reports are included. Cost/execution events are limited to the latest 100 saved events.

The exports were compared with saved data at {{export_verified_at}}. Direct-file browser verification was unavailable under the tool's URL policy. See the [verification scope and logs](../../log/viewer-experiments-html-export/README.md) for the recorded scope.

To export later data, use **Export run HTML ↓** in the [experiment viewer](http://127.0.0.1:8894). See the [execution and code guide](../../viewer/experiments/README.md).
