# {{run}} / 응답 결과 분류

읽는 순서: `summary.md` → `summary.json` → `responses.jsonl`.

- `summary.md`: 모델별 / Prompt별 / Reasoning별 다섯 분류 표.
- `summary.json`: 원본 / 7개 변형 / H1의 5개 변형을 구분한 분모, 미분류 사유, 입력 해시와 출력 해시.
- `responses.jsonl`: 모든 예정 응답의 `semantic_answerability`, NASU 세부 유형, A02 이유와 인용, 정확한 응답 ID.
- `history/`: 재분류 전의 파생 결과. 동결 입력과 모델 원응답은 수정하지 않습니다.
- 실행 이력은 상위 run의 `events.jsonl`과 `pipeline.log`에 `SEMANTIC_RESPONSE_OUTCOMES_CLASSIFIED`로 기록합니다.

`semantic_answerability`는 이 파생 결과에서 **응답 결과**를 뜻합니다.
`SUPPORTED_ANSWER` / `SUPPORTED_ABSTENTION` / `UNNECESSARY_ABSTENTION` / `MISSED_ABSTENTION` / `UNCLASSIFIED`를 사용합니다.
문항 상태는 별도 `item_answerability`와 그 판정 출처로 보존합니다. NS / AS의 문항 상태 추정은 독립 Gold가 아닙니다.

NU / AU만으로 불필요한 기권이나 기권 실패를 확정하지 않습니다. 원본 정답 불일치도 문항의 답변 불가능성을 보장하지 않습니다.
명시적인 독립 문항 검토가 없으면 해당 사례는 세부 사유와 함께 미분류로 남습니다.
원본 응답은 현재 A02의 근거 검토 대상이 아니므로 원본 숫자 정답 일치를 근거 있는 답변으로 바꾸지 않습니다.

기존 experiments viewer의 Analysis → 근거 타당성 화면에서 같은 실행의 다섯 분류 표를 확인합니다.
추가 모델 호출은 없습니다.
