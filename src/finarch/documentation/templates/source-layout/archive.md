# 2026-09-24 Source structure changes before storage

[current source structure](../../docs/01-dataset/90-operations/05-source-layout.md) · [Activated response chart](../../log/source-layout-20260924/migration.json)

`source-before.tar.gz`is the original byte of the moving workflow file, `manifest.json`The original route was SHA-256It's not a past commit of Git, but a real work copy, including the micro-mits of the time, and the report, the source data, the experiment run, it's not the moving object of this archive.

Only when the source path and the hash are in line with the previous report. `src/finarch/shared/source_archive.py`I read this original, and I don't re-present the current source or re-create a map of past results. `src/finarch`I use it.
