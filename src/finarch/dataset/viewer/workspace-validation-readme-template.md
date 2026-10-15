# Viewer 디렉터리 분리 확인

이 문서는 `src/finarch/dataset/viewer/workspace-validation-readme-template.md`에서 생성했습니다.

1. [폴더별 역할·실행 순서](../../viewer/README.md)
2. [HTTP 조회 확인 로그](validation.json)
3. [실제 데이터셋 화면](http://127.0.0.1:8893/dataset/?run=20260917-003&case=test-0001)

기존 HTML·실행 파일을 `viewer/dataset`으로 이동했고, 기존 실험 모듈은 `viewer/experiments`로 분리했습니다. 빌드 출력·서버 템플릿·실행 스크립트·관련 검사 파일의 경로를 바꿨습니다. Python 코드는 src 아래에 유지했습니다.

확인: Python 26개 통과, 메뉴 9개 검사 통과. 실제 브라우저에서 003의 717문항 목록과 test-0001 계산 그래프를 확인했으며 콘솔 오류가 없었습니다. 기본 주소·dataset 주소·로그 2개·실험 JS 두 주소는 HTTP 200입니다.

기존 `test_live_logs.cjs`는 로그 LLM 필터 예상 3건/실제 2건 불일치로 실패했습니다. 이동한 live.html의 내용은 변경하지 않았고, 이 검사는 파일 경로만 수정했습니다. 산술 뷰어 검사에서 빠진 임시 테스트 디렉터리 생성 한 줄은 보완했습니다. 모델 호출이나 실제 판정 저장은 하지 않았습니다.
