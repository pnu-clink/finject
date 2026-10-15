# 연구자료 HTML 내보내기 변경·확인 기록

2026-09-28 사용자 요청에 따라 연구자료 뷰어에 선택 문서의 HTML 내보내기를 추가했습니다. 논문 본문·가설·실험 응답은 변경 대상이 아닙니다.

## 읽는 순서

1. [연구자료 뷰어 안내](../../../viewer/research/README.md): 사용 방법과 구현 흐름
2. [확인 결과](verification.json): 다운로드·오프라인 표시·자료 전환·오류 처리와 검증 한계
3. [작업 로그](events.jsonl): 변경·확인 순서
4. [변경 전 원문 해시](source-hashes-before.json): 연구자료 원문 보존 확인 기준
5. [내보낸 한글 논문 예시](../../../outputs/research/20260928-html-export/20260924-paper-draft-research.html): 실제 버튼 다운로드로 만든 검증용 사본

|파일|역할|
|---|---|
|before-index.html|변경 전 뷰어 소스 사본; 별도 실행용 뷰어가 아님|
|before-README.md|변경 전 뷰어 README 사본|
|before-viewer-readme-template.md|변경 전 README 템플릿 사본|
|verification.json|실제 수행한 확인과 남은 한계|
|events.jsonl|시간이 있는 변경·확인 기록|
|source-hashes-before.json|5개 연구자료 원문의 변경 전 SHA-256|
|viewer-desktop.png / viewer-mobile.png|검증용 브라우저에서 확인한 버튼과 자료 화면|
|offline-desktop.png / offline-mobile.png|인터넷·JavaScript 없이 연 내보내기 파일 화면|

현재 소스를 읽힌 별도 Chromium에서 자료 5개 각각의 실제 다운로드·본문과 표 보존·오프라인 열기·목차 이동을 확인했습니다. 자료 로딩 중 버튼 잠금, 늦게 도착한 이전 응답 무시, 조회 실패와 내보내기 오류 후 재시도도 확인했습니다. 앱 내 브라우저 연결은 초기화 오류로 직접 확인하지 못했으며, 현재 실행 중인 서버 화면을 검증한 것으로 표시하지 않습니다.

사용 화면은 [연구자료 뷰어](http://127.0.0.1:8896/viewer/research/) 하나입니다. 이 폴더에 별도 결과 조회 화면을 만들지 않습니다. 내보내기는 원문을 새로 작성하거나 실험을 실행하지 않습니다. 이 README는 documentation/templates/research/viewer-export-log-readme.md에서 생성합니다.
