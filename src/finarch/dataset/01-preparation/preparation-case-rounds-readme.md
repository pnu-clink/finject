# Preparation case rounds

Read `active_round` and `rounds` in `run.json`, then the selected `NN-round/README.md`, followed by stages starting at `01-source`. For errors, read `06-exception-handler`; for the next round, inspect `00-round-input/seed.json`, each LLM job's `01-input/feedback-ref.json`, and `rendered-prompt.json`.

Each round has a separate folder and preserves earlier artifacts. REUSED entries in `00-round-input/seed.json` contain the original path and hash of copied files; distinguish reuse from new execution. Feedback originals remain under the failed round's `06-exception-handler/feedback/<target-round>/`; consuming stages save references. PENDING in `07-human-review` is not approval. Select the run, case, and round in the shared viewer.
