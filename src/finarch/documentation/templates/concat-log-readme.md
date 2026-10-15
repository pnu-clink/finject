# {output_name} · 작업 로그

데이터셋 화면은 [공통 viewer](http://127.0.0.1:8893/?run={output_name})에서 확인합니다. 여기서는 취합 근거만 보존합니다.

1. `concat-summary.json`: 전후 수량·증가/감소 ID.
2. `case-map.json`: 문항별 원천 run·교체 여부.
3. `question-revisions.json`: Preparation 후 저장된 질문의 표현 차이.
4. `concat-log.json`, `terminal.log`: 원천 해시·교체 작업.
5. `history-copy.json`, `full-view-validation.json`: 실제 단계 기록 복제·독립 파일 확인·원천 해시·7유형 통과 ID의 일치 검사.
6. `validation.json`: 파일 해시·정렬·상태 검사. 의미 검증이나 사람 승인은 아닙니다.
7. `export-check/`가 있으면 `validation.json` → `export-list.png` → `evaluation-sample.html` 순서로 평가자 Export의 목록·검사 범위·실제 배포 화면을 확인합니다. 샘플 HTML은 전체 데이터셋 Export가 아닙니다.
8. `export-seven-check/`가 있으면 `validation.json` → `export-policy.png` → `evaluation-sample.html` 순서로 7유형 전부 PASS·Reject 없음의 문항 단위 Export를 확인합니다. 한 유형이라도 실패·미평가·누락·Reject이면 문항 전체가 제외됩니다. `export-policy-check/`는 잘못 적용했던 유형별 선정의 과거 검사 기록이며 현재 기준이 아닙니다. 검사 범위와 전체 대상 수는 로그에 구분하여 기록합니다.

LLM 호출은 없습니다. 이전 보고서 화면의 캡처·검사 기록은 과거 확인 자료이며 최신 화면의 근거가 아닙니다.
