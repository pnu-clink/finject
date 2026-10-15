# ER-1 / ER-2 역산 Human annotation · $run

1. `$html`을 Chrome·Edge·Safari 등에서 열고 annotator 이름을 입력한 뒤 시작합니다. 이 HTML 한 파일에 id-0001~id-1354의 ER-1·ER-2, 실제 남은 Q/C, 제거 위치가 표시된 원본 Context, 영어 원판정과 한국어 표시 번역이 모두 들어 있습니다. 같은 ID의 ER-1은 왼쪽, ER-2는 오른쪽에 나란히 표시됩니다. 명칭은 `paper/TERMINOLOGY.md`를 따르며 내부 EA_01·EA_02 식별자는 유지합니다.
2. 왼쪽 **1 Accept / 3 Reject / 5 Pending**, 오른쪽 **2 Accept / 4 Reject / 6 Pending**입니다. Q/E는 표시 중인 이전·다음 ID, A/D는 같은 ID의 왼쪽·오른쪽 열 선택입니다. **?** 버튼 또는 키로 간략한 단축키 창을 열고 Esc로 닫습니다. Accept는 **현재 역산 판정(true·false)에 동의**한다는 뜻입니다. Pending도 확인 기록이며 미확인과 다릅니다. ID 옆 두 bullet은 ER-1·ER-2 순서로 Accept 초록 / Reject 빨강 / Pending 노랑 / 미확인 회색을 표시합니다. 판정 버튼과 저장된 판정 표시에도 같은 색상을 사용합니다. Reject·Pending을 선택하면 해당 열의 댓글 입력창으로 자동 이동합니다. ER-2의 Accept는 저장 후 현재 필터에 표시된 다음 문제로 이동하고 왼쪽 ER-1을 선택합니다. 마지막 문제에서는 현재 ID에 머무릅니다. Reject·Pending만 각 열의 댓글을 입력할 수 있습니다.
3. 현재 역산 판정 배지는 **true 녹색 / false 노란색**으로 강조합니다. 제거된 수치는 제작 당시 대상 기록과 원본의 정확한 위치를 대조해 **ER-1 분홍 취소선 / ER-2 보라 취소선**으로 표시합니다. 실제 남은 Q/C는 따로 표시합니다. 추가 원본 표시는 기존 역산 판정을 다시 계산하는 데 사용하지 않습니다. ER-2는 원본에서 독립적으로 다른 입력을 제거한 조건입니다. 두 열의 true/false 필터는 함께 만족하는 ID를 표시합니다. Export에는 필터와 관계없이 전체 문항이 들어 있습니다.
4. 이름별 브라우저 자동 저장, 중간 저장 JSON, JSON Import, 단일 HTML Export를 사용합니다. 이 버튼은 전체 문항·이름·판정·댓글·진행 위치·필터를 HTML 한 파일로 만들며, 파일 본문이 들어 있는 다운로드 링크도 표시합니다. 링크는 Export한 시점의 진행을 담습니다. 다른 컴퓨터에서는 JSON 또는 진행 포함 HTML로 이어서 작업합니다. Import는 결과 파일·문항 Q/C 해시, 중복, 판정·댓글 형식과 필터를 검사한 뒤 반영합니다. 같은 annotator의 더 최근 기록은 유지합니다. 이전 버전의 JSON도 이어서 사용할 수 있습니다.
5. `validation.json`에서 전체 수량·원본 해시·제거 대상 2,708개의 정확한 위치·외부 의존 여부·검증 범위를 확인합니다. `verification.log`에는 실제 실행한 로컬 검사와 브라우저 확인 요약이 있습니다.

공통 뷰어: [EA 비교 화면](http://127.0.0.1:8893/ea-inverse?run=$run&file=$snapshot)의 **Annotator용 HTML Export** 버튼으로도 같은 파일을 받습니다. **Annotator 화면 열기**는 HTML과 동일한 데이터·동작을 제공하는 로컬 미리보기입니다. 서버에는 annotation을 보내지 않습니다.

HTML 약 $megabytes MB · $cases개 ID / $items개 ER · 번역은 표시 보조 자료이며 영어 원판정을 덮어쓰지 않습니다. 외부 모델 호출 0건입니다. 생성된 배포용 HTML에는 판정 기록이 없습니다. QA용 이름·예시 판정은 실제 휴먼 검증 결과에 포함하지 않습니다.

검증 범위: $verification
