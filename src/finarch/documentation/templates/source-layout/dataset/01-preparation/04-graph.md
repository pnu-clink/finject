# 04-graph

[문서의 단계·요구·실행 흐름](../../../../../docs/01-dataset/01-preparation/04-graph/README.md) · [전체 소스 구조](../../../../../docs/01-dataset/90-operations/05-source-layout.md)

이 폴더는 위 문서 단계의 실행 코드를 소유합니다. 결과의 물리 경로는 기존 run 계약을 따릅니다.

|파일|역할|
|---|---|
|[preparation_diagnostic_graph.py](preparation_diagnostic_graph.py)|Expose the executed POT graph without certifying a mismatched answer.|
|[preparation_graph_repair.py](preparation_graph_repair.py)|Rebuild failed graphs after a verified syntax-only working-program correction.|
|[rebuild_preparation_graph.py](rebuild_preparation_graph.py)|Rebuild a saved POT graph locally while preserving review and failure history.|
|[stage.py](stage.py)|Ordered stage subjobs; artifact paths retain their existing contract.|
