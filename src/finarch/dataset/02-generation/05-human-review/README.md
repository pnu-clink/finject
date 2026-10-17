# 05-human-review

[Step of the letter: yoga; action flow](../../../../../docs/01-dataset/02-generation/05-human-review/README.md) · [A whole source structure](../../../../../docs/01-dataset/90-operations/05-source-layout.md)

This folder owns the execution code for the documented stage. Output paths follow the existing run contract.

|File|Role|
|---|---|
|[human_review.py](human_review.py)|Stage internal processing and inspection|
|[promote_evidence_candidate.py](promote_evidence_candidate.py)|Publish a saved candidate only after local schema, source and calculation checks.|
|[stage.py](stage.py)|Persist pending human review without approving a variant.|
