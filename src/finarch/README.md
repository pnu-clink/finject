# Source code reading order

1. [Dataset](dataset/README.md): source inputs, construction, and publication.
2. [Experiments](experiments/README.md): target-model requests, execution, saved results, and comparisons.
3. [Dashboard](dashboard/README.md): saved data, metric extraction, and visual summaries.

Server code is in each area's `viewer` package. Browser assets and launchers are under the top-level [viewer](../../viewer/README.md). Shared provider connections and logging are under `shared`; documentation generation is under `documentation`; common project paths are defined in `paths.py`.
