# EA 역산 검토 기록

실행 상태: **{status}**. 역할: `{role}`.

이 호출에는 삭제 후 질문·본문만 전달합니다. true/false는 LLM의 역산 판단이며 둘 다 제작을 계속합니다. 호출·응답 실패는 false가 아닙니다. Python은 응답 형식·인용 위치·파일 연결만 확인하며 식을 풀거나 의미를 재판정하지 않습니다.

읽는 순서:

1. `01-input/qc.json`: 실제 검토 Q/C. 해시 `{observation_sha256}`.
2. `01-input/prompt.md`, `response-schema.json`: 지침·응답 계약.
3. `02-call/`: 요청·원응답·사용량·실행 로그·응답 검사. 미호출이면 일부 파일이 없습니다.
4. `03-result/inverse-review.json`: 상태와 LLM 원판정·근거·식.
5. `03-result/evidence-display-check.json`: 표시 좌표 점검. 유일한 인용만 위치를 보정하며 원응답은 보존합니다.

`01-input/private.ref.json`은 제작 연결 기록이며 모델에 보내지 않습니다. `latest.ref.json`은 상위 폴더에서 최신 원본의 경로·해시만 가리킵니다.

공통 `viewer/dataset`에서 이 실행의 EA 유형 → **03-validation / 05-human-review**를 선택하면 근거 하이라이트와 식을 확인합니다. 저장 성공과 화면 확인은 구별합니다.
