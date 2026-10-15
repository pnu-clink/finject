# Annotation 화면 소스

[전체 사용 안내](../../../annotation/README.md) · [제작 뷰어](../README.md) · [요구사항과 실제 흐름](../../../docs/01-dataset/90-operations/04-viewer.md).

|파일|입력 → 처리 → 출력|
|---|---|
|[index.html](index.html)|날짜·데이터셋·파일 선택 → 데이터셋 강조·집계·전부 성공/전부 성공외 목록·유형 체크박스·비교 표·본문 맨 아래 한 줄 관리자 입력/오른쪽 저장|
|[manager.js](manager.js)|현재 Annotation 자료 → 날짜별 비교 전환·성공외 유형 표시·n명 판정·V에서 현재 필터/검색 유지·표시 유형 안에서 이동·기존 목록 유지 → 비교 화면·결과 JSON·G02 새 탭|
|[reviews.js](reviews.js)|활성 문항·유형·관리자 기록 → 하단 한 줄 입력·2/3 저장 포커스·4 입력 포커스·유형별 초안·수동 저장/수정·저장 기록 펼치기·목록 체크박스 → HTML/ZIP 다운로드|
|[reviewer.html](reviewer.html)|내보낼 요청·본인 평가·검증된 전체 본문 → 인라인 자료를 읽는 단일 템플릿 → 서버 연결 없이 검색·종류 선택·Q/E 이동|
|[style.css](style.css)|7개 유형·n명 평가자 → 100% 글씨·기본 여백·평가자 40%/유형·본문 60%·두 줄 유형/상태·세 줄 미리보기·38px 주석 입력·명확한 빨강/노랑 표시 → PC 전용 배치·내용에 따라 페이지 스크롤|
|[normalize.py](../../../src/finarch/dataset/viewer/annotation/normalize.py)|실제 2개 Export 계약 → 결정 가능한 형식 보완·명시된 데이터셋/실행 메타데이터 보존 → 보완본·변경 전후·미해결 오류|
|[agreement.py](../../../src/finarch/dataset/viewer/annotation/agreement.py)|문제·유형·평가자·명시 실행 → 유일한 배포본에 한해 비교 범위 연결·공통 저장 판정 대조 → Cohen/Fleiss κ·일치율·분모|
|[store.py](../../../src/finarch/dataset/viewer/annotation/store.py)|annotation/날짜의 JSON → 원본 해시·날짜별 비교 목록 중복 제거·독립 보완본·로그·README → 단일 화면이 읽는 현재 결과|
|[sources.py](../../../src/finarch/dataset/viewer/annotation/sources.py)|실행·원본 출처·취합 해시·저장 편집 → source type·출처 근거|
|[links.py](../../../src/finarch/dataset/viewer/annotation/links.py)|선택 문제의 7유형 → 저장 편집·전체 본문·차수 대조 → G02 URL 또는 미확인 이유|
|[reviews.py](../../../src/finarch/dataset/viewer/annotation/reviews.py)|선택 유형의 3구분 요청 → 문의 주석 선택 사항·수정 내용 필수·입력 해시·수신자·저장 버전 검사 → 독립 기록·변경 이력·내부 확인 제외·수신자별 HTML 자료|
|[review_export.py](../../../src/finarch/dataset/viewer/annotation/review_export.py)|수신자 요청·템플릿 → 안전한 인라인 JSON 삽입 → 독립 HTML|
|[G02 comparison.js](../prepare/generation/common/02-generate-text/comparison.js)|같은 문제·유형의 저장된 G02 원본·생성 본문 → 전체 비교·직접 연결의 본문 위치 이동|

서버는 [dataset/viewer/server.py](../../../src/finarch/dataset/viewer/server.py)의 `/annotation/`, `/api/annotation`·`/api/annotation/catalog`과 전용 파일·새로고침·등록·`/api/annotation/g02`·`/api/annotation/manager-review`·`/api/annotation/review-files`·`/api/annotation/review-export` 경로입니다. 기존 loopback·Origin 검사를 등록과 관리자 저장에도 적용합니다. Python 코드는 `src/finarch` 안에 있습니다. 화면은 원본 제작 판정 저장 API를 호출하지 않습니다. 전달용 HTML은 다운로드할 때 템플릿에 자료를 넣어 생성하며 템플릿 자체는 입력 자료가 없는 소스입니다.
