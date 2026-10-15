# 03-calculation

[문서의 단계·요구·실행 흐름](../../../../../docs/01-dataset/01-preparation/03-calculation/README.md) · [전체 소스 구조](../../../../../docs/01-dataset/90-operations/05-source-layout.md)

이 폴더는 위 문서 단계의 실행 코드를 소유합니다. 결과의 물리 경로는 기존 run 계약을 따릅니다.

|파일|역할|
|---|---|
|[diagnostics.py](diagnostics.py)|Preserve and sandbox-run POT before provenance acceptance; never promote it.|
|[preparation_repairs.py](preparation_repairs.py)|Preserve originals while validating bounded source and arithmetic repairs.|
|[preparation_resume.py](preparation_resume.py)|Retry a failed independent calculation without replacing earlier evidence.|
|[stage.py](stage.py)|Ordered stage subjobs; artifact paths retain their existing contract.|
