# {model} · E04 응답 형식 검사

호출 방식 `{transport}` · 계획 {planned}회 · 형식 통과 {valid}회.

1. [요청 manifest](../../02_request/{model}/manifest.jsonl): 실제 prompt·schema·Q/C·precision·실험 조건.
2. [LLM 실행 기록](../../03_execution/{model}/): Batch 전송·원응답·문항별 요청/응답 묶음.
3. [결과 목록](results.jsonl) · [형식 검사 집계](summary.json).
4. [Analysis](../../../02_analysis/README.md): 정답 숫자 비교·내용 검토·조건 비교.

형식 검사 결과에는 원본 정답 비교를 넣지 않습니다. 정답 참조는 Analysis에서 사용합니다. 원응답과 시도별 기록을 보존하며 미실행·실패·미평가를 구분합니다.
