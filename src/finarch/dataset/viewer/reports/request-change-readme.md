# LLM 호출 변경 비교

1. REQUEST-CHANGE-REPORT.md: 프롬프트·입력·스키마·응답 차이와 선택 첨부 기록.
2. request-change-report.json: 동일 자료를 공유 뷰어에서 표시하는 데이터. before/after.path가 실제 호출 단계 폴더입니다.
3. request-change-events.jsonl: 산출물 저장 이력(실행 로그 구조에 따름).

이전·이후 LLM 단계 폴더를 --before, --after로 명시합니다. 각 폴더의 실제 전송 기록을 읽으며 새 모델 호출은 하지 않습니다. --validation, --local-repair는 선택 첨부입니다. 없는 기록을 통과나 보정 없음으로 추정하지 않습니다. 코드 없는 생성·검사 응답도 JSON 전체를 비교합니다. 기존 호출 기록과 사람 판정은 수정하지 않습니다.

Preparation에서 비교 JSON이 있는 문항의 ‘LLM 요청 변경 전후’ 버튼으로 확인합니다. 자동 배치 생성 연결은 별도이며 이 함수 자체는 명시된 두 호출을 비교합니다.
