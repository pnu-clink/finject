# 05-human-review

[문서의 단계·요구·실행 흐름](../../../../../docs/01-dataset/02-generation/05-human-review/README.md) · [전체 소스 구조](../../../../../docs/01-dataset/90-operations/05-source-layout.md)

이 폴더는 위 문서 단계의 실행 코드를 소유합니다. 결과의 물리 경로는 기존 run 계약을 따릅니다.

|파일|역할|
|---|---|
|[human_review.py](human_review.py)|단계 내부 처리·검사|
|[promote_evidence_candidate.py](promote_evidence_candidate.py)|Publish a saved candidate only after local schema, source and calculation checks.|
|[stage.py](stage.py)|Persist pending human review without approving a variant.|
