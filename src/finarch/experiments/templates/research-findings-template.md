# {run} · 파일 흐름 확인과 분석

원본 {originals}개·변형 {variants}개, 대상 모델 풀이 {planned}회입니다. {analysis_model} · {effort} · {backend}로 분석했습니다. 파일 흐름과 잠정 관찰을 확인하는 소규모 실행이며 사용자 검토·개선안 채택은 **대기**입니다.

## 단계별 완료 상태

|단계|입력 → 처리 → 산출물|현재 결과|
|---|---|---|
|00 Input|dataset results → Q/C·precision / 평가 참조 분리|원본 {originals}·변형 {variants}|
|E01–E02|실험 조건·프로필 → prompt·schema·모델별 manifest|{planned}개 요청 고정|
|E03–E04|{solver_models} → 원응답 보존·형식 검사|형식 통과 {valid}/{planned}|
|A01|원본 숫자 비교·독립 문항 검토·익명 응답 검토|숫자 비교 가능한 원본 응답 중 일치 {numeric_matches}/{numeric_compared}|
|A02|조건별 대응 비교·반례 연결|내용 판정 가능 {assessed}/{planned} · 미평가 {unassessed}|
|A03|전체 통계·선정 사례 → 비판적 검토|[분석 원판정](results.jsonl)·이 보고서|

형식 통과, 원본 숫자 일치, 분석자가 판정한 대응의 타당성은 다른 값입니다. 숫자를 제출하지 않은 원본 응답은 숫자 비교 분모에 들어가지 않으므로 위 비율을 전체 원본 정답률로 사용하지 않습니다. 미해결 응답은 타당성 비율의 분모에서 제외하되 전체 계획 분모와 함께 표시합니다.

## 원본·7유형 × 4조건

각 셀은 **타당한 대응 / 내용 판정 가능 (미평가)**입니다. 같은 원문에 연결된 변형·조건은 독립 표본이 아닙니다.

{matrix}

## 관찰·반례·개선 제안

{notes}

## 실행 조건과 비용

- 이번 풀이의 실제 출력 상한: **{run_output_limit}토큰**. 새 기본 API 프로필은 **65,536토큰**이며 이미 실행된 요청에 소급 적용하지 않았습니다.
- `thinking_budget: 2048`은 Luna 전송 본문에 적용되지 않았습니다. 새 요청 생성에서는 제거했고, 추론은 OFF=`none` / ON=`medium`으로 설정합니다.
- 분석: **{analysis_model} · {effort} · {backend}**. Codex 분석에는 API의 출력 상한을 적용했다고 표시하지 않습니다.
- 풀이 Native Batch 비용 추정: **${cost:.8f}**. 반환 토큰과 단가로 계산한 값이며 청구서 대조 값은 아닙니다.
- {analysis_billing} 연구 해석용 상세 사례는 의도적으로 선택했으며 전체 비율은 A02 전체 집계에서만 가져왔습니다.

## 파일 읽는 순서

1. [실행 설정](../../config.json), [입력 안내](../../00_input/README.md).
2. [E02 prompt·schema·요청](../../01_evaluation/02_request/README.md) → [E03 원응답](../../01_evaluation/03_execution/README.md) → [E04 형식 검사](../../01_evaluation/04_validation/README.md).
3. [A01 문항·응답 분석](../01_response_review/README.md) → [A02 조건·유형 비교](../02_comparison/README.md).
4. [A03 요청과 제공된 근거](manifest.jsonl) → [영어 원판정](results.jsonl) → 이 한국어 검토 안내.

[뷰어에서 이 실행 보기](http://127.0.0.1:8894/?run={run}&tab=analysis). 원응답·기존 판정은 보존하며, 개선안의 적용과 후속 실험·논문 결론 채택은 사용자 토의 이후입니다.
