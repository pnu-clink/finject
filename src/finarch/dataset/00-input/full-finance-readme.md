# FinanceReasoning 전체 실행용 입력

원천 {total}건을 조사했습니다. 출처 선택 조건으로 제외된 문항은 {source_filtered}건이며, 대상 안에서 빈 본문 {empty_context}건, boolean 정답 {boolean_answer}건, 질문·본문이 정확히 같은 중복 {duplicate_qc}건을 제외한 **{count}건**입니다. 선택 조건과 기존 번호 대응은 selection-manifest.json에 기록합니다. 공백뿐 아니라 JSON으로 저장된 빈 배열·객체·문자열과 null도 빈 본문입니다. 원천 파일은 변경하지 않았습니다. 새 Preparation을 위한 입력 준비이며 LLM 검증 완료가 아닙니다.

1. `preparation-result.json`: 입력 생성·스키마·원천 해시 검사 결과와 개수.
2. `selection-log.json`: 제외 이유, 원본 ID, 중복 대표 ID.
3. `selection-manifest.json`: 입력/원천 해시, 선택 정책, 새 ID와 raw_id 대응.
4. `input.json`: ID → raw_id → Q → C → 정답 메타데이터 순서의 실행 입력.
5. `provider-records.json`: 변경하지 않은 원본 자료의 보관본. 원본 풀이를 POT 요청으로 전달하지 않습니다.
6. `code-syntax-audit.json`: 원본 `python_solution`의 Python AST 조사. 유형 간 중복이 있으며 새 POT의 실패 건수가 아닙니다. 원본 코드를 실행하지 않았습니다.

같은 C라도 Q가 다르면 유지합니다. Q와 C가 모두 같은 경우 easy → medium → hard 및 원본 파일 순서상 첫 문항을 남깁니다. 옛 LLM 결과·피드백·통과 기록은 가져오지 않습니다.

Finance 어댑터는 실제 context가 비어 있지 않은 JSON 객체·표 문자열 배열이면 표로 변환하고, 일반 본문이면 그대로 구성합니다. 원래 자료형과 숫자 표기·원문 위치는 json_source에 보존합니다. 출처 ID만으로 JSON 여부를 결정하지 않습니다. provider-records.json에는 변환 전 원문을 보관하며 PoT 숫자 위치는 새 context에서 등록합니다. 이는 입력 구조 검사이며 풀이 정답이나 의미 검증은 아닙니다.
