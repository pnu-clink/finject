# v0.26 그림 표시·HTML 내보내기 확인 기록

2026-09-28 사용자 요청에 따라 기존 v0.26의 SVG 2개를 연구자료 뷰어에서 표시하고 HTML에 함께 내장하도록 보완했습니다. 원문에 이미 있는 이미지 문법이 일반 텍스트로 표시되던 문제를 수정한 작업이며, 논문 내용이나 그림 자체를 새로 작성하지 않았습니다.

## 읽는 순서

1. [뷰어 안내](../../../viewer/research/README.md): 사용 방법·파일 책임·현재 처리 흐름
2. [확인 결과](verification.json): 실제 수행한 표시·다운로드·오프라인·오류 처리 검증
3. [그림을 포함한 HTML 예시](../../../outputs/research/20260928-image-export/20260924-paper-draft-research.html): 실제 버튼 다운로드로 만든 사본
4. [작업 로그](events.jsonl)와 [변경 전 원문·그림 해시](source-hashes-before.json): 변경 범위와 자료 보존

|파일|역할|
|---|---|
|before-index.html|변경 전 뷰어 소스 보관본; 별도 실행용 뷰어가 아님|
|before-viewer-readme-template.md|변경 전 안내 템플릿|
|verification.json|실제 확인 결과와 직접 확인하지 못한 범위|
|events.jsonl|시간이 있는 원인·변경·확인 기록|
|source-hashes-before.json|연구 문서 5개와 SVG 2개의 변경 전 해시|
|viewer-overview.png / viewer-detail.png|별도 검증 브라우저에 표시된 개요도·상세도|
|offline-overview.png / offline-mobile.png|인터넷·JavaScript 없이 연 그림 포함 HTML|
|offline-mobile-original-size.png|오프라인 모바일 화면에서 원본 크기로 확대하고 그림 영역 안에서 스크롤하는 상태|

현재 소스를 읽힌 별도 Chromium에서 자료 5개의 다운로드·오프라인 열기를 확인했습니다. v0.26은 SVG 2개의 내장 바이트가 원본과 동일했고, 오프라인 표시·JavaScript 없는 확대·390px 화면의 가로 넘침 방지가 통과했습니다. 이미지 로딩 중 잠금, 이전 선택의 늦은 이미지 응답 무시, 파일 누락·잘못된 형식·손상된 SVG의 오류 표시와 복구도 확인했습니다. 처음 발견한 긴 본문 경로의 모바일 넘침은 줄바꿈으로 보완했고, 실패 기록과 재확인 결과를 로그에 구별해 남겼습니다.

사용 화면은 [연구자료 뷰어](http://127.0.0.1:8896/viewer/research/) 하나입니다. 이 폴더에 별도 결과 조회 화면을 만들지 않습니다. 본문·그림 원본과 실험 응답을 변경하거나 모델을 호출하지 않습니다. 앱 내 브라우저에 대한 접근은 관리자 정책 확인 실패로 허용되지 않았으므로, 실행 중인 화면의 직접 확인과 프로젝트 파일을 이용한 별도 검증을 구별합니다.

이 README는 documentation/templates/research/viewer-image-log-readme.md에서 생성합니다.
