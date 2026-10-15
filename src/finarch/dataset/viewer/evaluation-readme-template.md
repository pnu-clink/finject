# 평가 HTML 검증 산출물

이 문서는 `src/finarch/dataset/viewer/evaluation-readme-template.md`로 생성했습니다.

1. [사용 방법과 구현](../../docs/76-offline-evaluation-export.md)을 먼저 읽습니다.
2. [검증 로그](validation.json): 실행·문항 수·파일 크기·생성 시간·검사 결과.
3. [검증용 평가 화면](evaluation-sample.html): 20260917-002와 003에서 각각 test-0001, test-0002를 넣은 단일 HTML입니다. 전체 실행 배포본이 아닙니다.

LLM 호출과 원본 판정 변경은 없습니다. 실제 배포 파일은 공통 뷰어 최상단의 `평가용 HTML Export`에서 대상 실행과 필터를 선택해 만듭니다. 평가자는 이름 입력 → 단계 확인 → 판정 저장 → 임시 저장/결과 Export 순으로 사용합니다. 재개 시 Import에서 임시 기록이나 JSON 파일을 선택합니다.
