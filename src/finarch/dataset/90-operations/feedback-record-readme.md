# 다음 차수의 문항별 피드백

`feedback.json`은 이 문항·유형의 이전 오류에서 만들어진 보완 지시 원본입니다. source_round는 발생 차수, target_round는 적용 차수, target_role/target_step은 소비 위치입니다. source는 기존 오류·피드백의 근거 위치입니다.

읽는 순서: source 근거 → feedback.json → 다음 호출 입력의 feedback-ref.json → rendered-prompt.json → 실제 API/CLI 요청.

소비 단계는 원본 내용과 SHA-256을 대조하고 실제 전송 지시문에 포함됐는지 확인합니다. 파일을 수정하여 과거 참조를 무효화하지 마세요. 새 보완은 다음 차수에 별도로 기록합니다. 참조만 생성한 것은 모델 호출 성공이 아닙니다. 공통 뷰어의 해당 단계 ‘사용한 프롬프트·입력 보기’에서 적용 여부와 저장된 지시문을 확인합니다.
