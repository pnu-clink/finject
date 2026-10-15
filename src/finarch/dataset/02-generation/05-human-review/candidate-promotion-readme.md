# 검증 후보 반영

1. candidate-promotion.json: 새 후보 출처와 실제 검증 결과.
2. candidate-promotion-history: 반영 전 계산·그래프·자동 판정 보존.
3. 03-calculation: 검증한 후보 코드·Python 실행·정답 대조.
4. 04-graph: 같은 코드로 다시 생성하고 대조한 그래프.
5. run.json: 재검증 후 현재 자동 판정. 사람 판정은 별도이며 변경하지 않습니다.

뷰어 03과 04에서 현재 코드·참조·그래프를 확인합니다. 참조의 적용 가정은 계속 검토 대상으로 남습니다. 원래 LLM 호출은 보존하며 새 코드의 실제 호출 위치는 candidate-promotion.json의 candidate를 따릅니다. 추가 LLM 호출은 없습니다.
