# 응답 형식 V4 로컬 검사

상태: **{status}** · 오프라인 검사 {tests}개 통과 · 새 모델 호출 {calls}건.

## 읽는 순서

1. `verification.json`: 검사 결과·프롬프트/스키마 해시·V2·평면 V3 호환 확인.
2. `tests.log`: 실제 검사 로그.
3. `request-example.json`: 합성 Q/C와 소수 자릿수·프롬프트·스키마.
4. `provider-request-example.json`: 실제 전달 방식과 동일하게 구성한 Gemini 요청 예시(전송하지 않음).
5. `expected-response-example.json`: 형식 검사용 예상 응답. LLM 출력이 아닙니다.

실제 프로그램과 규칙: [응답 형식 안내](../../../../docs/02-experiments/README.md).
새 모델 응답의 준수율은 미실측입니다. 기존 exp-003의 고정 manifest와 V2 요청 검사를 통과했습니다.
