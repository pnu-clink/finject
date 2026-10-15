# 데이터 제작 부록과 연구 뷰어 문자 크기 정리

2026-09-28 사용자 요청: 논문의 4.2·4.3에 축약한 데이터 생성 전체 로직을 부록으로 제공하고, 제목 아래 본문의 불규칙한 크기와 큰 그림 설명을 정리합니다.

## 읽는 순서

1. [논문 v0.27](../../../reports/run/20260924-paper-draft/PAPER-KO.md)의 부록 B 또는 [부록 편집 원본](../../../reports/run/20260924-paper-draft/DATA-GENERATION-APPENDIX.md)을 읽습니다.
2. [파일별 순서도](../../../reports/run/20260924-paper-draft/DATA-GENERATION-FLOWS.md)와 [근거 장부](../../../reports/run/20260924-paper-draft/DATA-GENERATION-EVIDENCE.json)에서 현재 구현·저장 사례·확인 시점을 대조합니다.
3. [공통 연구 뷰어](http://127.0.0.1:8896/viewer/research/#s14)에서 한글 논문 v0.27을 선택하거나 [검사한 HTML 사본](../../../outputs/research/20260928-appendix-typography/20260924-paper-draft-research.html)을 엽니다.
4. [확인 결과](verification.json)와 [작업 로그](events.jsonl)를 읽습니다. 저장 파일 검사·분리된 브라우저 검사·사용자 직접 확인은 구별합니다.

## 변경과 파일 역할

|파일|역할|
|---|---|
|before-index.html, before-runs.json, before-README.md|뷰어 수정 전 파일|
|verification.json|자료별 본문·표 크기, 캡션, 순서, 다운로드·오프라인 검사|
|events.jsonl|변경·확인·실패와 보완의 순서|
|typography-desktop.png, typography-mobile.png|3.5 첫 문단과 후속 문단의 같은 크기 확인 화면|
|figure-desktop.png, appendix-desktop.png|그림 캡션과 부록 표시 확인 화면|

첫 문단만 19px, 나머지는 16px로 지정하던 규칙을 제거했습니다. 본문과 표는 상위 본문 크기를 상속하며 데스크톱 17px, 모바일 16px입니다. 제목은 별도의 크기를 유지하고 그림 상세 설명은 15px 캡션으로 묶었습니다. 소절의 표를 소절 밖에 추가하던 순서 문제도 수정했습니다. 링크와 코드 표기를 지원하여 부록의 실제 근거를 찾을 수 있게 했습니다.

## 확인 범위

현재 파일을 분리된 Chromium의 입력으로 제공하는 화면·내보내기 검사를 사용합니다. 실제 localhost 서비스나 사용자 브라우저에 접속한 검사와 구별하며, 사용자 확인 완료를 주장하지 않습니다. 검사할 HTML은 outputs 아래에만 저장합니다. reports/run마다 별도 뷰어를 만들지 않습니다.

실험·생성·Evaluation·Analysis·모델 호출은 수행하지 않습니다. 논문 결과와 결론, RQ·SQ·H 및 기존 그림 원본은 유지합니다. 이 README는 documentation/templates/research/viewer-appendix-log-readme.md에서 생성합니다.
