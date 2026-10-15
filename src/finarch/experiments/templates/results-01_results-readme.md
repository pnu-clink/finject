# A01 — 결과 취합

{source}에서 계획된 {planned}개 요청을 연결했습니다. 저장 상태: {statuses}.

- [responses.jsonl](responses.jsonl): 요청/응답 ID, 네 응답 필드, 조건, 기존 숫자 비교와 출처.
- [state.json](state.json): 취합 수와 처리 상태.
- 원응답은 각 행의 result_path, 수치 평가는 evaluation_source가 가리키는 기존 기록입니다.

원응답·판정을 수정하거나 문항을 다시 풀지 않았습니다. 다음 단계는 [A02 관계 비교](../02_comparison/README.md)입니다.

## 사용법

상위 pipeline의 Analysis가 이 단계의 저장 자료 취합을 먼저 수행합니다. A01 자체는 Python 처리이며 모델 호출 0건입니다. 일반 analysis 명령은 A02/A03까지 이어질 수 있으므로 A01만 실행하는 명령으로 취급하지 않습니다. 자료 해시 불일치·누락을 정답 추정으로 보완하지 않습니다.
