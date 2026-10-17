# 02-review

[Step of the letter: yoga; action flow](../../../../../docs/01-dataset/01-preparation/02-review/README.md) · [A whole source structure](../../../../../docs/01-dataset/90-operations/05-source-layout.md)

This folder owns the execution code for the documented stage. Output paths follow the existing run contract.

|File|Role|
|---|---|
|[question_precision.py](question_precision.py)|Align explicit decimal-place instructions with the preserved gold precision.|
|[revisions.py](revisions.py)|Preserve originals while validating bounded source and arithmetic repairs.|
|[stage.py](stage.py)|Review source once per outer round, preserving constrained corrections.|
