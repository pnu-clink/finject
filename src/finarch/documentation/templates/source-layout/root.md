# 소스 코드 읽는 순서

1. [문서 단계와 소스 구조](../../docs/01-dataset/90-operations/05-source-layout.md)를 먼저 확인합니다.
2. [dataset](dataset/README.md): 데이터셋 입력·제작·전달.
3. [experiments](experiments/README.md): 대상 모델 요청·호출·결과·비교.
4. [dashboard](dashboard/README.md): 저장 자료·수치 추출·숫자 화면.

서버 코드는 각 영역의 `viewer`, 브라우저 자산과 실행 파일은 최상위 [viewer](../../viewer/README.md)에 있습니다. 공통 모델 연결·로그는 `shared`, 문서 생성은 `documentation`, 공통 경로는 `paths.py`입니다.
