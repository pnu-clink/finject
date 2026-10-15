# {total}문항 균형 개발 데이터

원문 Q·C 기준으로 문맥 내 풀이 후보 {per_cohort}개와 외부 금융 공식이 필요한 후보 {per_cohort}개를 예비 선별했습니다. 개별 원인과 모호성은 Preparation에서 검토합니다. 전체 모집단의 대표 표본은 아닙니다. 외부군은 공식·정의 의존 사례이며 실시간 외부 표 조회 실험은 포함하지 않습니다.

읽는 순서: `selection-manifest.json`(원천 경로·해시·선정 이유·예상군) → `input.json`(QCA/type/precision) → `provider-records.json`(private 원천 보존) → `preparation-result.json`(무결성 결과). 선정 기대값은 모델 입력에 넣지 않고 실제 검증 판정과 별도로 유지합니다.

Preparation 실행 후 단일 viewer에서 해당 run을 선택하면 원문·코드·검증·차수별 피드백을 확인할 수 있습니다. 이 데이터 생성은 모델 호출이 아닙니다.

## 입력 필드 표시 순서

`id → raw_id → question → context → reference_answer → reference_answer_type → reference_precision → answer_metadata → 기타 항목` 순서로 저장합니다. 필드명과 값은 유지하며 JSON 키 순서만 변경합니다. 기존 실행 기록은 변경하지 않습니다.
