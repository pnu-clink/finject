# Fin-o1 회수·등록 이력

기존 공통 실험 구조로 등록한 run: **$runs**.

이 폴더는 임시 회수 폴더의 과거 위치 변경·해시 검사·색인 기록을 보존합니다. 실제 입력은 각 run의 `00_input`, 요청은 E02, 원응답·수신 기록은 E03 모델별 `calls`와 `source-stage`, 결과는 E04에서 읽습니다.

- `recovery-index.original.txt`: 최초 임시 회수 색인 원문. 안의 경로는 과거 위치입니다.
- `verification.json`, `relocation-receipt.json`: 당시 해시와 위치 기록.
- `finalization-receipt.json`: 기존 구조 등록 확인·이력 보존 해시.
- 모델별 등록 로그는 E03 모델 폴더의 `pipeline.log`, 회수 로그는 같은 모델의 `source-stage/recovery.log`입니다.

이 안내는 pipeline.py report-a100-stages가 템플릿에서 생성합니다. 추가 모델 호출은 0건입니다.
