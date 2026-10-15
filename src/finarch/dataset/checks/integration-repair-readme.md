# Generation 검사 코드 정비

이번 변경은 검사 입력·기대값·호출 방식의 수정입니다. 실제 생성·판정 로직, 원문, 과거 실행 결과는 변경하지 않았습니다. API 호출은 0회입니다.

|항목|변경 및 확인|
|---|---|
|EA 기본 동작|현재 필수 수식 역산 검사는 옛 optional 검사 설정과 별개로 기록되는지 확인합니다.|
|EA 복원 판정|기존 식·삭제 편집·남은 Q/C 근거 연결이 갖춰진 검사 입력으로 복원 가능 판정과 근거를 확인합니다.|
|EA 미평가|근거 연결이 없으면 NOT_EVALUATED와 이유를 기록하고, 기존 PASS/FAIL과 이유를 유지하는지 확인합니다.|
|IC-RELATION|임시 폴더를 먼저 만들고 과거 run 없이 검사 입력을 구성합니다. Python·그래프·정답 대조 후 최종 답이 같으면 후보 등록을 막는지 확인합니다.|
|IC-SOURCE|import_module로 모듈을 불러온 뒤 patch.object를 사용합니다. 폴더 이름은 유지합니다.|
|추가 검사 입력 보정|사용하지 않는 fact를 제거하고, private 기록 변경에 따른 전체 입력 해시 변화와 실제 역산 결과·근거 불변을 구분합니다.|

결과: **{count}개 통과**, 실행 시간 {seconds}초. 이는 로컬 검사 결과이며 FinanceReasoning 실제 API 실행이나 전체 생성 성공률이 아닙니다.

읽는 순서: 이 문서 → integration-repair-checks.json → integration-repair.log. 공통 viewer에서 이 run의 ‘후속 통합검사’를 펼치면 현재 결과를 확인할 수 있습니다. legacy-integration.log는 수정 전 오류 기록으로 보존합니다.

책임: `checks/test_ea_recovery.py`, `test_generation_python_gates.py`는 EA와 SOURCE 판정·근거를 확인합니다. `test_relation_plan.py`는 임시 입력과 후보 등록 차단을, `test_source_from_value.py`는 VALUE에서 SOURCE로 출처 문구만 추가되는지 확인합니다. 모두 Python 검사이며 실제 LLM 호출은 하지 않습니다.
