# Analysis 동시 호출

- 기록 시각: {updated_at}
- 단계·상태: {stage} · {status}
- 동시 호출 한도: **{current_limit}건** / 실행 중: **{active_calls}건** / 대기: {queued_calls}건
- 누적 실패: {deferred_failure_count}건 / 실행·미전송 건수와 별도로 보존합니다.
- 제어 방식: {mode} / 전체 CPU 평균: **{cpu}**
- 규칙: {interval}초마다 CPU가 {threshold}% 이하이면 한도를 {growth}% 증가시키고 정수로 올림합니다. 초과하거나 측정에 실패하면 증가하지 않습니다. 남은 요청 수까지만 증가합니다.

## 읽는 순서

1. [runtime-schedule.json](runtime-schedule.json): 이 run에 명시적으로 적용한 운영 설정입니다. 파일이 없으면 동결 설정을 사용합니다.
2. [scheduler.json](scheduler.json): 현재 한도·진행 건수·마지막 CPU 측정값입니다.
3. [events.jsonl](../events.jsonl): 설정 변경과 주기별 CPU 측정·한도 변경 이력입니다.
4. [timing.md](timing.md): 실제 단계·호출 시간과 병목입니다.

실험 뷰어의 Analysis에서 같은 파일을 읽습니다. CPU는 이 컴퓨터 전체의 사용률이며 제공자의 처리 여유를 측정한 값이 아닙니다. 개별 오류는 별도 보존하고 빈 실행 슬롯을 먼저 채웁니다. 관리되는 단계의 승인된 오류 재시도는 미전송·실행 중 요청이 모두 0인 뒤 기존 최대 3회 회차에서 수행합니다. 동결한 모델·프롬프트·스키마·입력은 유지됩니다.
