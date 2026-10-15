# $model — 완료 자료 회수

- 고정 revision: `$revision`
- 원격 자료 위치: `$source`
- 로컬 실험 자료 위치: `$local_root`
- 요청·수집: **$requests건**
- 원격 형식 검사 기록: `$statuses` (정답 여부와는 별개입니다.)
- 원응답 해시 검사: $requests건. 로컬 파일 해시 검사: $files개.
- 회수 압축 SHA-256: `$archive_sha256`
- 회수 명령은 `experiments/pipeline.py recover-a100-stage`입니다. 추가 모델 호출은 0건입니다.

## 읽는 순서

1. [recovery-receipt.json](recovery-receipt.json): 위치·회수 시간·해시 확인 기록.
2. [동결 준비 기록](remote-evidence/prepared.json): 원본 manifest 위치·해시·모델 설정.
3. [수집 인덱스](remote-evidence/collection-index.json): 수신·형식·사용 토큰 집계.
4. [취합 응답](collection/responses.jsonl): 응답과 원격 원응답 위치. 원격 절대 경로는 원기록입니다.
5. `remote-results/<trial_id>/`: provider-request.json, raw-response.json, delivery.json, format-check.json 원본.
6. `remote-evidence/01_evaluation/02_request/`: 입력·영어 프롬프트·응답 스키마가 행별 저장된 원격 manifest.
7. [실행 상태](remote-evidence/state.json), `remote-evidence/events.jsonl`, `remote-evidence/telemetry.jsonl`: 완료 상태·이벤트·자원 측정.
8. [_recovery/manifest.json](_recovery/manifest.json): 원격에서 기록하고 로컬에서 대조한 파일별 해시.

## 조회와 처리 범위

Codex 파일 뷰어에서 이 README와 위 링크를 열어 실제 회수 파일을 확인합니다.
이번 산출물은 원격 완료 자료를 그대로 보존한 회수본입니다. 실험 뷰어용 새 run 등록·로컬 E04 재검사·Analysis 실행은 포함하지 않습니다.
모델 가중치·런타임 캐시 디렉터리는 회수 대상에서 제외합니다. 요청·원응답·취합본·최상위 실행 기록·control 기록은 보존합니다.
