# {title}

{change_description}

동일 입력 확인: {same_input}. 원문 {input_count}건이며 입력 파일 해시와 문항 목록을 비교했습니다.

{summary}

위 통과·실패는 자동 검사 결과입니다. 상위 단계 제외, 미생성, 미평가는 통과로 세지 않습니다. 차수 사이에는 같은 실행에서 통과한 결과를 유지하며 실패한 유형과 그 의존 결과만 다시 검사했습니다. 비교 실행은 코드부터 새로 호출했습니다.

같은 변형 대상: {same_target_count}개. 변형 대상 변경: {different_target_count}개. 새 코드가 다른 수치를 선택한 경우 동일 조건 비교와 구분합니다. {evaluation_note} 같은 원문을 사용한 개발 비교이며 별도 데이터의 일반화 결과가 아닙니다.

## 읽는 순서

1. `input-selection.json`: 원문 목록과 해시.
2. `initial-feedback.json`, `feedback/`: 처음부터 적용한 지침과 출처.
3. `comparison-report.json`: 문항·유형별 차수 결과, 원인, 새 실패와 해결, 호출·토큰 집계.
4. 각 차수의 `05-text/03-final-validator/03-result.json`: 최종 반복 여부.
5. 문항별 번호 폴더: 실제 요청, 원응답, 검사와 적용 결과. 원응답을 수정하지 않았습니다.

[뷰어에서 비교 실행 열기](http://127.0.0.1:8893/?run={comparison_run}&round=01-round&case=test-0001&tab=dtt). 차수 표시 다음의 **{title}** 버튼에서 전체 표를 볼 수 있습니다.

로그는 `log/run/{comparison_run}`의 같은 차수·문항·단계 경로에 있습니다. `default.log`에는 모든 기록이 시간순으로 모이며 각 행은 JSON입니다.
