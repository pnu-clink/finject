# {date} 회의록 안내

자료 접수일은 {date}이며 실제 회의 날짜·절대 시각은 확인되지 않았습니다. 화자 1=최동희 교수, 화자 2=박우익은 사용자가 직접 확인했습니다.

## 읽는 순서

1. [회의록 본문](MINUTES.md): 핵심 요약 → 결정과 보류 → 할 일 → 지난 회의 대비 변화 → 주제별 논의 → 미결 질문.
2. 로컬 누적 회의록 `{archive_html}#m-{date}`: 앞선 네 회의와 함께 선택해 읽는 단일 HTML 화면입니다.
3. A100의 기존 회의록 주소 `{published_url}#m-{date}`: **{publish_status}**
4. [구조화된 회의 데이터](meeting.json), [사용자 확인 화자](speaker-confirmation.json), [사용자 제공 전사](transcript.txt).
5. [작성·배포 시도 로그](events.jsonl), [검증 결과](verification.json), `before/`: 무엇을 작성했고 어디까지 확인했는지 및 이전 누적본을 확인합니다.

## 기록 범위

전사의 관찰·제안과 검증된 실험 결과를 구분했습니다. 80·31문항과 유형별 Reasoning OFF/ON 차이는 발언 중 언급된 수치·관찰로만 기록했습니다. 화자 확인은 완료했지만 참석자의 회의록 내용 승인은 받지 않았습니다. 게이트웨이·trajectory optimization은 구현·실험 결정으로 기록하지 않았습니다. 새 모델 호출은 하지 않았습니다.

새 회의록을 연구 복기 뷰어에 잘못 추가했다가 해당 연결을 제거하고 그때 시작한 로컬 서버를 종료했습니다. A100은 기존 `expl-20260822-172510.html` 한 항목을 갱신하는 방식이며 새 항목을 만들지 않습니다. 이 README는 `src/finarch/documentation/templates/meeting-readme.md`에서 생성합니다.
