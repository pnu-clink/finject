# Experiment-result viewer · viewer-exp v1

**[Open in a browser](http://127.0.0.1:8894/?run={{latest_run}}&tab=overview)**

This separate brown-themed viewer follows the existing data viewer's run selection, case list, and detail panels. It reads actual `reports/experiments-run` files. **Export run HTML** downloads the selected run as a separate file; HTML is not automatically generated in every result folder.

## Start the viewer

Run from the repository root. Node.js 20 or newer is required; no additional packages are needed. Recorded verification environment: `{{node_version}}`.

```bash
node src/finarch/experiments/viewer/server.mjs
```

The default address is `http://127.0.0.1:8894`. Use `--port 8904` for another port or `--root /absolute/experiments-run` for a different result collection. On macOS, use `start.command` in the corresponding viewer folder. Opening source `index.html` directly shows startup guidance. **Exported HTML is a separate copy that works without a server.**

## First reading order

1. **Overview:** select a run and inspect original/variant/request counts, collection states, and numeric-comparison denominators.
2. **Condition comparison:** select numbers in the model's Unguided Solving / Criteria-Guided Solving × Reasoning OFF / Reasoning ON table.
3. **Failure analysis:** distinguish unique request counts from potentially overlapping diagnostic reasons, then open a case.
4. **Case comparison:** inspect responses, evidence, exact requests, schemas, and raw outputs for the same Q/C and conditions. Select the **Input sent to the model** heading to collapse/expand the question, context, and analyst information. It starts expanded. Selecting evidence expands it and highlights the input. Original English responses are displayed unchanged.
5. **Cost and execution / Reports and history:** inspect run-wide saved tokens, costs, resources, Markdown analyses, and preserved earlier reports.

Search, run, filters, case, and view are stored in the URL. **Refresh** checks file changes and preserves expanded history in the current detail. **Download table** saves the filtered aggregates and case IDs as Markdown.

## Export run HTML

1. Select **Export run HTML ↓** at the top.
2. Choose a run, then **Create HTML file ↓**.
3. Open the downloaded `<run-id>-experiments.html` in a browser.

There is one HTML file per run. It starts with the current tab/filters but contains the **entire run**; reset filters to inspect all cases. Exporting a different run starts at Overview. The export includes six views, search, condition changes, case comparison, English raw responses, exact requests, schemas, original records, reports, and internal links. CSS, JavaScript, and compressed data are embedded; external connections are blocked.

Data are frozen at export time. Analyst-only original reference answers are included. Events use the same latest-100 limit as the viewer. Construction references outside the run and source files over the existing 8 MB limit are excluded. The header and affected links identify excluded large files. File changes during export or missing exact requests cause an error; incomplete HTML is not downloaded.

Use a recent browser with decompression support. One export is built at a time; closing the export dialog can cancel an active build. The CLI can also write to an explicit path without overwriting an existing file:

```bash
node src/finarch/experiments/viewer/scripts/export-html.mjs 20260920-exp-004 /absolute/path/20260920-exp-004-experiments.html
```

[Exported files from recorded verification](../../outputs/experiment-exports/README.md) · [HTML export verification records](../../log/viewer-experiments-html-export/README.md)

## File responsibilities

| File | Role |
| --- | --- |
| `index.html` | Run selection, list, filters, content, and source-file panel shell. |
| `styles.css` | Brown theme and responsive layout. |
| `app.js` | Six views, URL state, comparisons, evidence highlighting, and safe Markdown display. |
| `repository.mjs` | Experiment-folder boundaries, reads, partial-save handling, and exact response links. |
| `model.mjs` | Shared online/offline aggregation, filters, case selection, and table export. |
| `export-html.mjs` | Verify full-run data, compress cases, and assemble a single HTML. |
| `offline.mjs` | Decompress embedded data and serve the same views without network requests. |
| `server.mjs` | Local GET server on port 8894 by default. |
| `tests/repository.test.mjs` | Aggregates, failure bodies, path restrictions, partial saves, and read-only checks. |
| `tests/export-html.test.mjs` | Online/offline equivalence, raw responses, HTML safety, changes, cancellation, and missing files. |
| `scripts/verify.mjs` | Compare four actual runs, document/response links, and input/result hashes. |
| `scripts/export-html.mjs` | Save a single HTML for an explicit run/output path. |
| `scripts/verify-export.mjs` | Export an actual run, compare it with the source, and save logs. |
| `scripts/build-readme.mjs` | Generate README from templates and saved verification records. |
| `HANDOFF.md` | Earlier handoff sources and latest requirements. |

## Recorded verification

- Verification time: {{verified_at}}.
- {{tests}} automated local checks passed; {{run_count}} result runs were compared with actual files.
- **0 additional LLM calls.** Experiment input, request-manifest, and result SHA-256 hashes were unchanged.
- [Verification result](../../log/viewer-experiments-v1/verification.json) · [test log](../../log/viewer-experiments-v1/tests.log) · [browser record](../../log/viewer-experiments-v1/browser-checks.md).
- [File responsibilities and implementation flow](../../docs/viewer-experiments.md) · [handoff](HANDOFF.md).
- [Case-input collapse/expand checks](../../log/viewer-experiments-input-collapse/README.md).

Additional HTML export verification: **{{export_tests}} local checks passed**. **{{export_run_count}} copies** of exp-001–005 were compared against actual files for aggregates, responses, reports, activity, and before/after hashes. The browser confirmed exp-004 download and creation of the downloaded file. Direct `file://` opening was blocked by the browser tool's URL policy, so that screen verification was not completed. See the [recorded scope](../../log/viewer-experiments-html-export/browser-checks.md).

These are agent local/screen checks, not completed user review.

## Display scope

- VALID means format/consistency passed, not semantic correctness or abstention accuracy.
- Numeric comparisons use saved original-answer checks. Perturbed numeric comparison is not applicable.
- Case detail compares models under the same condition and may include counterpart responses outside the list's status/diagnostic filter.
- Costs, history, and documents cover the entire run; response filters do not recompute costs.
- Original reference answers are in an analyst-only collapsible area. A construction reference absent from the run is marked not included.
- During partial writes, the viewer retains the last valid data with an update warning. An initial read failure displays an error.
- The first version did not provide periodic auto-refresh, cross-run comparison, new semantic scoring, or saved human ratings.

This file is generated from `templates/README.template.md`. Run `node src/finarch/experiments/viewer/scripts/build-readme.mjs` to regenerate the guide.

## Read the experiment purpose first · 2026-09-22

Overview displays the selected run's `EXPERIMENT-PURPOSE.md` before result numbers. Read the purpose, comparison conditions, and actual implementation differences first. Missing documents are marked unregistered; another run's purpose is not substituted. Reports/history opens this document first. EXP-006 records limitations of comparing runs with/without abstention guidance.

## Collapse/expand the purpose

Select **What does this experiment examine?** to collapse or expand the purpose. It starts expanded and reads the existing run's purpose document unchanged.

## V5 response format

V5 has no status field. Saved checks display missing numeric answers separately; abstention status and appropriateness remain unevaluated. Unevaluated is not displayed as zero. The actual EXP-006 results remain V4; `revision-v5/README.md` in Reports/history contains later revision-review material.
