# 대시보드 기록 수치 추출

[문서의 단계·요구·실행 흐름](../../../../docs/03-dashboard/README.md) · [전체 소스 구조](../../../../docs/01-dataset/90-operations/05-source-layout.md)

이 폴더는 위 문서 단계의 실행 코드를 소유합니다. 결과의 물리 경로는 기존 run 계약을 따릅니다.

|파일|역할|
|---|---|
|[metrics.py](metrics.py)|Extract recorded metrics without estimating missing values or timestamps.|
