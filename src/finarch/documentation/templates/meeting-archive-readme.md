# {receipt_date} 회의록 안내

자료 접수일은 {receipt_date}입니다. {date_note} {speaker_note}

## 읽는 순서

1. [회의록 본문](MINUTES.md): 핵심 현황 → 결정과 보류 → 할 일 → 이전 회의 대비 변화 → 주제별 상세 → 미결 질문.
2. [누적 회의록 뷰어]({published_url}#m-{meeting_id}): A100의 기존 한 화면에서 회의를 선택해 읽습니다. {publish_status}
3. 로컬 누적본 `{archive_html}#m-{meeting_id}`: 같은 화면의 빌드 산출물입니다.
4. [구조화된 회의 데이터](meeting.json), [사용자 확인 날짜·화자](speaker-confirmation.json), [제공 전사 사본](transcript.txt): 회의록의 내용·출처를 확인합니다.
5. [검증 결과](verification.json), [작업 로그](events.jsonl), `before/`: 배포 결과와 변경 전 누적본을 확인합니다.

## 기록 범위

{scope_note}

회의록은 연구 방향을 기록한 문서이며 구현 완료·실험 결과·원문 논문 검증을 대신하지 않습니다. A100 배포는 기존 `expl-20260822-172510.html` 한 항목을 갱신하는 방식입니다. 이 README는 `src/finarch/documentation/templates/meeting-archive-readme.md`에서 생성했습니다.
