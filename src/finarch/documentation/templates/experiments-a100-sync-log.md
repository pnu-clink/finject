# PC ↔ A100 실험 동기화

상태: **$status** · 확인 시각: `$updated_at` (UTC)

공통 코드 해시: `$code_release`

A100 작업 경로: `$remote_workspace`

## 읽는 순서

1. [status.json](status.json): 코드·공개 입력 일치, 실행별 수신 상태, 오류.
2. [events.jsonl](events.jsonl): 주기별 확인 시각·코드 버전·실패 기록.
3. [process.json](process.json): 동기화 프로세스 PID·시작 시각·주기. PID 파일만으로 실행 중이라고 판단하지 않습니다.
4. 모델별 `*-remote-snapshot.json`: 서버가 공개한 완료 응답 해시·서버 실행 상태·옵션 기록.
5. 모델별 `*-received.json`: PC에서 확인한 실제 응답 해시와 변경 감지용 파일 정보.
6. [verification.json](verification.json): 로컬 검사·서버 확인·실제 수집 검증 범위와 미실행 항목.

공통 실험 뷰어의 **PC ↔ A100 동기화** 화면에서 같은 최신 status.json을 확인합니다. 모델별 진행 상태는 해당 실험의 E03 `sync-status.json`에도 저장합니다. 이 동기화는 모델 호출·Evaluation 완료 판정·Analysis를 실행하지 않습니다.

코드와 공개 입력은 PC → A100, 상태와 원응답은 A100 → PC입니다. private 정답·외부지식 분류·Analysis는 전송하지 않습니다. 기존 실험 입력과 원응답의 다른 해시는 덮어쓰지 않고 충돌로 기록합니다. 새 코드 릴리스는 다음 실행에 적용하며 실행 중인 프로세스의 코드를 바꾸지 않습니다.

PC의 중지·대기 상태는 코드나 공개 입력의 변경과 별도로 매 회차 확인하여 변경분을 `pc-state.json`에 전달합니다. 공통 실행기는 이 파일의 중지 상태를 읽고 새 요청 전송을 멈춥니다. 이전 실행기에서 이미 전송한 요청을 취소하는 기능은 아닙니다.

첫 검사에서는 실제 파일 해시를 계산합니다. 이후 원격 실행 상태의 완료 수·오류 수가 변하지 않으면 이전에 게시한 원응답 해시 목록을 사용합니다(`UNCHANGED_EXECUTION_PUBLISHED_HASHES`). PC에서는 파일 정보가 달라진 원응답을 다시 해시 검사합니다. `--sync-force`는 원격과 PC의 모든 원응답 바이트를 다시 확인합니다. 주기 검사와 전체 재검사의 범위를 구별합니다.

실행: `PYTHONPATH=src .venv/bin/python -B -m finarch.experiments.pipeline a100-sync --sync-action cycle`

주기 실행: 같은 명령의 `--sync-action watch`. 중지: 이 폴더에 `STOP` 파일을 만들면 현재 회차가 끝난 뒤 종료합니다. 자동 모델 요청은 없습니다.
