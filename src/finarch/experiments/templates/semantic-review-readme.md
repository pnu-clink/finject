# {{run}} · A01 LLM 내용 검토

풀이 대상에 전달한 Q/C·precision으로 입력의 답변 가능성을 먼저 검토합니다. 그 후 대상 모델의 실제 응답을 익명으로 검토합니다. 판정은 분석 LLM의 잠정 판단이며 gold·사람 승인과 구분합니다.

|단계|상태|분석 호출 수|사용량 기반 추정 비용 USD|
|---|---|---:|---:|
{{states}}

## 읽는 순서

1. `00-definition`: 각 분석 단계의 영문 prompt, 응답 JSON schema, 해시입니다. 2·3차도 같은 기준을 사용합니다.
2. `01-LLM-input`: 대상 모델 응답을 보지 않은 입력 검토입니다. `manifest.jsonl`은 Q/C·precision만 포함한 요청이고 `results.jsonl`은 판단·근거·사용량입니다. 2·3차는 1차의 동일 입력 판정·실패 기록을 공통 사용하므로 이 폴더를 새로 만들거나 비용을 다시 합산하지 않습니다.
3. `02-LLM-response`: 형식을 통과한 실제 응답을 문항별로 검토합니다. 조건명을 숨기고 응답 번호 순서를 섞으며, 번호와 실험 조건의 연결은 manifest에만 기록합니다. 평가에 필요한 별도 정답 정보는 대상 모델에 전달하지 않습니다.
4. `03-LLM-audit`: 첫 분석의 결과별 최대 8개 응답을 재계산하여 판단을 재검토합니다. 첫 응답 판정은 보여주지 않습니다. 판단이 다르면 삭제하지 않고 기본 적절률에서 미해결로 표시합니다. 이 표본의 불일치율은 전체 평가 오류율 추정치가 아닙니다.
5. `../02_comparison/summary.json`: 유형×P0/P1×OFF/ON, 원문 숫자 일치별 변형 결과, 대응 전환과 원문 군집 재표집 구간입니다. `rows.jsonl`과 `counterexamples.jsonl`에서 원기록으로 연결합니다.

각 LLM 폴더의 `batch-001/input.jsonl`은 OpenAI Batch 전송 형식입니다. `job.json`은 제공자 Batch ID·상태, `output.jsonl`·`errors.jsonl`은 반환 원문이며 입력·원응답을 덮어쓰지 않습니다. `state.json`은 수집·사용량·무결성 기록입니다. 실행 로그는 run의 `events.jsonl`에 남깁니다.

실행 파일은 `src/finarch/experiments/02-analysis/legacy/content-analysis/semantic_review.py`, 응답 검사는 `semantic_contract.py`입니다. 뷰어의 **02 Analysis**에서 같은 저장 결과를 읽습니다. 형식 실패·분석 실패·판정 미해결은 의미 오답으로 강제 변경하지 않습니다. 같은 Luna 계열로 풀이·분석했으므로 공유 오류 가능성이 남습니다.
