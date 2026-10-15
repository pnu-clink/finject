# 실험 뷰어 HTML Export 확인 자료

`src/finarch/experiments/viewer/templates/export-log-readme.template.md`에서 자동 생성했습니다.

1. [브라우저 확인](browser-checks.md): 버튼·모달·다운로드 파일과 확인하지 못한 범위.
2. [검증 결과](verification.json): exp-001~005의 실제 요청·파일 수, 표본 상세 대조, 입력/요청/결과의 전후 SHA-256.
3. [로컬 검사](tests.log): {{export_tests}}개 통과. 온라인/오프라인 동등성, 원기록/링크, HTML 삽입 문자열, 변경·누락·취소·경로 경계를 검사합니다.
4. [생성 로그](build.log): 문항별 압축 진행과 회차별 결과.
5. [실제 서버 로그](server.jsonl): 내보내기 HTTP 응답과 파일 크기. 서버가 실행 중이면 추가됩니다.

검증 시각: {{export_verified_at}}. 실험 실행·LLM 호출은 **0회**, 원본 입력·결과 파일 쓰기는 **0개**입니다.

[회차별 HTML 목록](../../outputs/experiment-exports/README.md) · [뷰어 시작·사용법](../../viewer/experiments/README.md) · [책임 표·흐름도](../../docs/viewer-experiments.md)

직접 HTML 파일을 여는 화면 확인은 브라우저 도구의 URL 정책에 막혔습니다. 다운로드와 자료 대조를 사용자 열람 완료로 표현하지 않습니다.
