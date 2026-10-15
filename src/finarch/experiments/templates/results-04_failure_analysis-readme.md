# A02 실패·검토 불가 자료 분석

실행: {run}. 현재 검토 미완료·불가 자료: {count}건. Python이 저장된 자료만 취합하며 새 모델 호출은 없습니다.

1. `summary.json`: 전체 검토 모수·상태별 수·재검토 필요 여부·문항별 페이지 위치입니다.
2. `page-*/summary.json`: 질문·문맥, 대상 Evaluation 모델이 실제 반환한 answer/classification/explanation/evidence, 형식 오류, Analysis 검토 사유·인용·호출 오류입니다.
3. 실험 뷰어의 **02 Analysis → A02 실패·검토 불가 자료**에서 상태별로 고른 뒤 원문과 응답을 함께 확인합니다.

미검토(NOT_REVIEWED)·검토 실패(REVIEW_FAILED)는 재검토 대상이고 해결 전에는 A03 진행을 막습니다. 검토 불가(NOT_REVIEWABLE)·입력 원문 없음(SOURCE_MISSING)은 사유를 보존하며 A03를 막지 않습니다. 원응답과 점수는 변경하지 않습니다. 대상 모델의 출력 오류와 분석 호출의 기계적 오류는 별도로 표시합니다.
