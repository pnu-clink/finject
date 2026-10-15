# $run_id — A100 공개 실험 입력

이 폴더는 PC에서 해시 검증 후 동기화한 공개 입력 패키지입니다. 이 파일 전달만으로 모델 실행을 시작하지 않습니다.

- 공통 코드 버전: `$code_release`
- 공개 입력 묶음 SHA-256: `$input_digest`
- 실제 입력 목록·파일별 해시: `sync-input.json`
- PC 실행 제어의 수신 사본: `pc-state.json`

읽는 순서: `config.json` → `00_input/public.jsonl` → `01_evaluation/02_request/`의 프롬프트·스키마·모델별 manifest → E01 `a100-runtime.json` → 실행 후 E03 모델 폴더의 `runtime-provenance.json`, `remote-state.json`, `remote-results/`.

private 정답·외부지식 분류와 Analysis는 PC에 보존합니다. 로컬 E04 형식·수치 검사와 실험 viewer 반영은 PC의 공통 동기화 pipeline이 담당합니다. 기존 동결 입력과 원응답의 다른 해시는 덮어쓰지 않습니다.
