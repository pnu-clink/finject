# Annotation 처리 코드

[상위 뷰어 코드](../README.md) · [요구·책임·실제 순서도](../../../../../docs/01-dataset/90-operations/04-viewer.md).

|파일|입력 → 처리 → 출력|
|---|---|
|[normalize.py](normalize.py)|실제 annotator/evaluator JSON → 확정 가능한 형식 보완 → 보완본·변경 전후·미해결 오류|
|[agreement.py](agreement.py)|문제·유형·평가자별 저장 판정 → 동일 자료·공통 평가 매칭 → 7개 유형별 Cohen/Fleiss κ와 분모|
|[store.py](store.py)|annotation/날짜의 원본 → 해시·현재 자료·별도 보완본·로그·템플릿 README·G02 선택 문제 조회 → 조회 API 자료|
|[sources.py](sources.py)|취합 원본·manifest 해시·실행 정보 또는 정확한 변경 본문 → 출처 대조 → source type·조회 근거·종류별 문항 수|
|[links.py](links.py)|현재 선택의 7유형·지정 차수·저장 편집·전체 본문 → 유형별 대조·기록 계승 확인 → G02 직접 URL·생성 차수·본문 해시 또는 미확인 이유|
|[reviews.py](reviews.py)|현재 입력·관리자 요청/주석 → 문의 주석 선택 사항·수정 내용 필수·입력 해시·저장 버전·수신자 검사 → 독립 관리자 상태·변경 이력·수신자 요청·전체 본문·HTML/ZIP|
|[review_export.py](review_export.py)|수신자 요청과 단일 템플릿 → 안전한 인라인 JSON 삽입 → 서버 연결 없이 읽는 HTML|

읽는 순서는 `store.py` → `normalize.py` → `agreement.py` → `sources.py` → `links.py` → `reviews.py` → `review_export.py`입니다. 원본 계약과 현재 입력의 역할은 [입력 안내](../../../../../annotation/README.md)를 따릅니다. Python은 제작 데이터·대상 모델 실험을 실행하지 않습니다.
