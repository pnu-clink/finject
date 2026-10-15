# EA 역산 검토 소규모 확인

상태 **{status}** · 응답 완료 **{completed}/6** · true **{inverse_true}** · false **{inverse_false}** · 검토 오류 **{errors}**.

기존 EA 본문 6건을 복사해 **역산 검토 호출만** 추가합니다. 문장을 새로 생성하거나 제작 판정을 다시 검증한 실행이 아닙니다. 원래 통과/실패와 원본 파일을 보존하며 `source_reuse`로 복사 출처를 표시합니다.

- 모델: `luna-low-api` · `gpt-5.6-luna` · 추론 low. 운영은 기존 G03 검증 프로필을 따릅니다.
- 새 호출 최대 6회, 자동 재시도 0회. 모델에는 삭제 후 Q/C 두 필드만 전달합니다.
- 기존 비중·세금 사례 3건과 남은 정보가 부족한 기존 EA 3건을 사용합니다. 결과는 LLM 판단이며 정확도 측정값이 아닙니다.

읽는 순서:

1. `pilot-selection.json`: 실제 원본 경로·해시·문항/유형.
2. `pilot-results.json`, `summary.json`: 개별 역산 판정과 제작 상태 유지 확인.
3. `02-generation/01-round/test-xxxx/<EA>/03-validation/07-ea-inverse-review/attempt-001/`: 프롬프트·응답 스키마·요청·원응답·사용량·표시 검사·판정.
4. `logs/`: 로컬 검사와 소규모 호출 출력. `api-usage/summary.json`: 실제 토큰에 따른 예상 비용이며 청구 금액 확정값은 아닙니다.
5. `verification.json`: 원본 해시·개별 판정 유지·인용 표시 검사와 실제 화면 확인 기록.

공통 뷰어에서 이 run → EA 유형 → `03-validation` 또는 `05-human-review`를 엽니다. 본문 근거는 노란색, 복원식은 별도 상자에 표시합니다. 문장 감사가 이번 실행에서 새로 수행된 것으로 해석하지 않습니다.

관련 Python 검사 56개, 표시용 JavaScript 검사와 문서 연결 검사를 통과했습니다. 실제 호출의 판정은 정확도 측정이 아니며, 본문에 근거가 있는지와 식의 타당성은 사람이 검토합니다. 구형 전체 검사에는 이전 자료 경로·모델 기본값·미등록 역할 문제들이 남아 있어 프로젝트 전체 검사 통과를 의미하지 않습니다.

저장 자료 확인을 반복할 때에는 `PYTHONPATH=src .venv/bin/python -m finarch.dataset.checks.ea_inverse_review_pilot --output reports/run/20261001-ea-inverse-review-pilot --verify-only`를 사용합니다. 이 명령은 모델 호출을 하지 않습니다.

[사람 검토 화면 캡처](screenshots/g05-inverse-review.jpg) · [실제 화면 확인 내역](viewer-verification.json)
