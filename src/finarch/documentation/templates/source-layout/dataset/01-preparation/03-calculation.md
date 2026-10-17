# 03-calculation

[Step of the letter: yoga; action flow](../../../../../docs/01-dataset/01-preparation/03-calculation/README.md) · [A whole source structure](../../../../../docs/01-dataset/90-operations/05-source-layout.md)

This folder owns the execution code for the documented stage. Output paths follow the existing run contract.

|File|Role|
|---|---|
|[diagnostics.py](diagnostics.py)|Preserve and sandbox-run POT before provenance acceptance; never promote it.|
|[preparation_repairs.py](preparation_repairs.py)|Preserve originals while validating bounded source and arithmetic repairs.|
|[preparation_resume.py](preparation_resume.py)|Retry a failed independent calculation without replacing earlier evidence.|
|[stage.py](stage.py)|Ordered stage subjobs; artifact paths retain their existing contract.|
