# 원본 source type 필터 검증

읽는 순서: validation.json → filter.jpg → 현행 뷰어 문서.

- validation.json: 실제 데이터와 브라우저 필터 개수 검증 기록입니다.
- filter.jpg: 전체 출처 선택을 복원한 실제 화면입니다.
- ../../docs/01-dataset/90-operations/04-viewer.md: 파일 역할과 처리 흐름입니다.
- ../../viewer/dataset/source-type.js: 기록된 provenance를 원본 출처로 구분합니다.

TAT-QA 단독 선택 288문항, 전체 선택 2050문항을 확인했습니다. 모델 호출과 데이터 재처리는 하지 않았습니다.
