# {run} — 저장된 응답의 관계 분석

**Evaluation 출처: {source}.** 분석은 저장된 풀이·평가 결과를 사용하며 대상 모델을 다시 호출하지 않습니다. {execution_note}

|범위|저장 결과|
|---|---|
|전체 계획 응답|{total}개; 원본 {original_count}개에서 파생된 실험 조건|
|형식 통과|{valid}개|
|숫자 / null|{numeric} / {null}개|
|원본의 기존 숫자 비교|{originals}|
|응답 해석|{observations}개 관찰에서 {cited}개 응답을 근거로 연결|

응답 수는 독립 문항 수가 아닙니다. 같은 원본에서 파생된 변형·풀이 지시·추론 조건을 비교합니다. 숫자 일치, 모델 classification, 설명에 적힌 풀이 방식, 분석자의 연구 해석을 구분합니다. 문항 답변 가능성을 재검증하거나 gold를 다시 작성하지 않습니다. 숫자 비교의 원출처는 A01의 evaluation_source에 기록합니다.

[분석 전체](../README.md) · [원문 해석 자료](../02_comparison/interpretations.jsonl) · [집계 자료](../02_comparison/comparisons.json)

{body}
