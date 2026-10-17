# 04-graph

[Step of the letter: yoga; action flow](../../../../../docs/01-dataset/01-preparation/04-graph/README.md) · [A whole source structure](../../../../../docs/01-dataset/90-operations/05-source-layout.md)

This folder owns the execution code for the documented stage. Output paths follow the existing run contract.

|File|Role|
|---|---|
|[preparation_diagnostic_graph.py](preparation_diagnostic_graph.py)|Expose the executed POT graph without certifying a mismatched answer.|
|[preparation_graph_repair.py](preparation_graph_repair.py)|Rebuild failed graphs after a verified syntax-only working-program correction.|
|[rebuild_preparation_graph.py](rebuild_preparation_graph.py)|Rebuild a saved POT graph locally while preserving review and failure history.|
|[stage.py](stage.py)|Ordered stage subjobs; artifact paths retain their existing contract.|
