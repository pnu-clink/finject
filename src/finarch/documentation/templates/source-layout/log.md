# Source area, stage order, verification record

[Source definition and pipeline response](../../docs/01-dataset/90-operations/05-source-layout.md) → [Three servers running](../../viewer/README.md) → [Exam summary](verification.json) in this order.

- `migration.json`Move the file hash before the previous path. `final-layout.json`I'm going to write it down together.
- `before-python.json`, `after-python.json`Offline testing, like after-the-move, blocks the CLI external network model.
- `regression-comparison.json`: Comparison between existing failures and new failures.
- `dataset-js-comparison.json`: Pre-screen scan comparison of data sets running with the same storage data.
- `relocation-regressions.log`, `shared-tests.log`: moving path; dashboard; general runner; pass source conservation inspection.
- `experiment-viewer-tests.log`The following are the test results:
- `docs-validation.json`: document;README template; archival copy; and hashing.
- `browser-checks.json`: Real server screen check.

This task changes the source structure and does not perform model call-to-experiment re-executing.](../../archive/20260924-source-layout/README.md)They don't report that they've passed the entire test until they've failed the previous test.
