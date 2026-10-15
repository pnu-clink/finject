# A02 — 관계 비교와 응답 근거 해석

출처 {source}의 {planned}개 응답, 대응 비교 {pairs}쌍. 상태: {status}.

1. [comparisons.json](comparisons.json): 전체·유형×4조건 분포, 동일 조건 원본 정오별 관계, 앞뒤/출처/EA/지시/추론 전이, 실제 응답 ID와 분모. `original_external_knowledge`가 있으면 원본 제작 분류별 수치를 따로 표시합니다.
2. [interpretations.jsonl](interpretations.jsonl): 응답의 풀이 방식·분류/설명 관계·반례. 모델이 반환한 classification과 별도입니다.
3. V2 요청에서 생성되는 `response-assessments.jsonl`: 변형 응답별 기권 이유·결정 근거 판정, 인용·검토 상태·조건·요청 해시.
4. V2의 `response-assessment-summary.json`과 `response-assessment-coverage.json`: 계획 분모를 유지한 Python 집계와 미검토·실패 현황. 실제 판정은 LLM 판단이며 사람 검증 정답을 뜻하지 않습니다.
5. [state.json](state.json): 집계와 해석의 실제 처리 상태.

숫자가 A/B 후보와 같다는 관찰은 선호나 타당성 판정이 아닙니다. IC-source는 각각 VALUE 부모와 연결하며 현행 자료에서 출처와 뒤쪽 위치 효과는 분리되지 않습니다. EA의 숫자 일치만으로 역산이라고 부르지 않습니다. 다음 단계는 [A03 연구 해석](../03_research/README.md)입니다.

원본 외부사용 분류는 대상 모델의 실제 외부지식 사용을 측정한 값이 아닙니다. `CRITERIA_NOT_MET`를 비사용 집단으로 해석하지 않습니다.

## 사용법

상위 Analysis pipeline이 A01 취합 후 집계와 원본별 LLM 관계 해석을 이어갑니다. 요청 수·완료·미해석은 manifest와 coverage/state를 함께 확인합니다. 저장 집계만 갱신할 때는 프로젝트 루트에서 `PYTHONPATH=src .venv/bin/python -u -B -m finarch.experiments.pipeline analysis --aggregate-only --run reports/experiments-run/{run}`을 사용합니다. 새 모델 호출 0건이며 기존 실행 상태와 A03를 완료로 바꾸지 않습니다.
