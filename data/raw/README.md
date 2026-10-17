# Pinned source datasets

These are the distributed source files before this project's preparation and transformation. Their original bytes are preserved. FinanceReasoning easy and TAT-QA were copied from the local pinned sources and checked by SHA-256; medium/hard were downloaded from the same pinned FinanceReasoning revision and checked against the official file inventory. Records and answers were not rewritten. A distributed source dataset is not necessarily an unmodified financial filing; distinguish each upstream dataset's construction method.

| File | Contents | Source records |
| --- | --- | ---: |
| [FinanceReasoning easy](finance-easy.json) | Questions, contexts, answers, and upstream solutions | 1,000 |
| [FinanceReasoning medium](finance-medium.json) | Medium-difficulty distributed records | 1,000 |
| [FinanceReasoning hard](finance-hard.json) | Hard-difficulty distributed records | 238 |
| [TAT-QA dev](tatqa-dev.json) | Documents containing tables, paragraphs, and multiple questions | 278 documents |

[manifest.json](manifest.json) records source URLs, pinned revisions, hashes, sizes, record counts, and import provenance. [finance-upstream-files.json](finance-upstream-files.json) is the official file inventory used for medium/hard verification.

Check provenance and hashes, then use [config/source-catalog.json](../../config/source-catalog.json) or the [small source sample](../sample/README.md). Preparation reads raw files and writes a new prepared folder. Keep source versions separate and preserve their manifests. Upstream reference answers and solutions are construction material; send only the frozen public inputs to target models.
