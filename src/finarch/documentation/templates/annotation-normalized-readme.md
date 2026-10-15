# 형식 보완 JSON

[상위 입력과 읽는 순서](../README.md)를 먼저 확인합니다. 각 JSON은 날짜 폴더의 같은 이름 원본에 형식 보완만 적용한 파일입니다. 12자리 접두사는 원본 SHA-256의 앞부분입니다. `annotator / labels` 또는 `finarch-evaluation-results-v1`의 입력 구조를 유지합니다.

판정·주석·추가/삭제 본문은 그대로입니다. 변경 전후는 `../_manager/normalization-log.jsonl`, 현재 집계는 `../_manager/summary.json`에서 확인합니다. 관리자 화면은 최상위 원본을 다시 읽기 때문에 이 보완 폴더를 두 번째 annotator 입력으로 세지 않습니다.
