# 대시보드 독립 서버

[문서의 단계·요구·실행 흐름](../../../../docs/03-dashboard/README.md) · [전체 소스 구조](../../../../docs/01-dataset/90-operations/05-source-layout.md)

이 폴더는 위 문서 단계의 실행 코드를 소유합니다. 결과의 물리 경로는 기존 run 계약을 따릅니다.

|파일|역할|
|---|---|
|[resources.py](resources.py)|프로젝트 현황과 기존 숫자 화면의 파일·읽기 전용 API·허용 원문 참조를 연결합니다.|
|[server.py](server.py)|8895 독립 서버. `/`는 프로젝트 현황으로 보내며 미등록 원문 참조는 404로 종료합니다.|
