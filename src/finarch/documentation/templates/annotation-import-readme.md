# {run} · 평가 Import 변환본

대상 HTML: `{html_path}`  
배포본 ID: `{package_id}`  
차수: `{round}` · 전체 {case_count}문항

1. 대상 HTML의 **Import**에서 `{first_file}` 또는 `{second_file}`을 선택합니다. 평가자별로 별도의 브라우저 탭에서 작업하면 서로의 판정을 덮어쓰지 않습니다.
2. `validation.json`: 원본·HTML 해시, 실제 포함/제외 수, 판정·주석·본문·시각 보존 검사, 실제 Import 함수 검사.
3. `excluded-*.json`: 재생성되었거나 대상 배포본에 없는 이전 평가를 원문 그대로 보존합니다. Import용 파일이 아닙니다.
4. `terminal.log`: 변환·검사 실행 결과.

`id/type/note`를 `case/variant/comment`로 바꾸고 `accept/reject/pending`을 `APPROVED/REJECTED/PENDING`으로 변환했습니다. 기록된 판정에만 `confirmed: true`를 사용하고 확인하지 않은 체크 항목은 만들지 않습니다. EA의 표시 이름만 현재 EA-01/EA-02로 맞춥니다.

원본은 상위 폴더에서 그대로 보존합니다. 재생성한 문항에 이전 판정을 이식하지 않습니다. 새 문항의 판정은 비워 두며 자동 Accept로 채우지 않습니다. Import는 평가자 HTML 안의 독립 기록이며 제작 데이터의 판정을 변경하지 않습니다. 이 폴더는 관리자가 자동으로 읽는 날짜 폴더의 추가 입력이 아닙니다.
