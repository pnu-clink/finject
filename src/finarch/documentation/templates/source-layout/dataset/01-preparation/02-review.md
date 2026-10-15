# 02-review

[문서의 단계·요구·실행 흐름](../../../../../docs/01-dataset/01-preparation/02-review/README.md) · [전체 소스 구조](../../../../../docs/01-dataset/90-operations/05-source-layout.md)

이 폴더는 위 문서 단계의 실행 코드를 소유합니다. 결과의 물리 경로는 기존 run 계약을 따릅니다.

|파일|역할|
|---|---|
|[question_precision.py](question_precision.py)|Align explicit decimal-place instructions with the preserved gold precision.|
|[revisions.py](revisions.py)|Preserve originals while validating bounded source and arithmetic repairs.|
|[stage.py](stage.py)|Review source once per outer round, preserving constrained corrections.|
