# 실행 로그

실행: `{run_id}`

모든 `.log` 파일은 JSON Lines입니다. 입출력의 줄바꿈은 문자열 안의 `\n`으로 저장하므로 기록 하나가 물리적인 한 줄입니다.

| 파일 | 내용 |
|---|---|
| `../../cli.log` | 실제 CLI 시작 직전 argv·작업 디렉터리. run_id로 실행을 구분합니다. |
| `pipeline.log` | 중요 기능의 호출 시작. 입출력이나 내부 함수 상세는 없습니다. |
| `detail.log` | 기능명을 JSON key로 둔 상세 기록. 요청·응답·산출물 내용·실패·시간을 포함합니다. |
| `llm-ic-value.log` | IC-VALUE 생성 및 검토 |
| `llm-ic-source.log` | IC-SOURCE 생성 및 검토 |
| `llm-ic-relation.log` | IC-RELATION 생성 및 검토 |
| `llm-ea.log` | EA 생성 및 검토 |
| `llm.log` | POT 등 위 네 유형 이외의 LLM 기록 |
| `default.log` | 위 파일에 기록한 모든 행을 실행 전체 순서대로 함께 저장 |

처음에는 `default.log`, 호출 흐름만 볼 때는 `pipeline.log`를 읽습니다.
`function`과 같은 이름의 key 안에 본문이 있습니다. 같은 기능이 여러 번 호출되면 `call_id`와 `problem_id`로 구분합니다.
중첩된 내부 처리도 상위 중요 기능명으로 검색됩니다. `detail.log`의 내부 `function`에는 실제 내부 함수명이 남습니다.

`grep -F 'dtt.realize' detail.log`로 해당 기능의 상세 기록을 찾을 수 있습니다.

전용 뷰어: http://127.0.0.1:8893/logs?run={run_id}
실행·파일 선택, 기능명/본문 검색, 입출력 펼치기, 2초 자동 갱신을 제공합니다.
파일의 `sequence`는 실행 전체 순번이므로 개별 파일에서는 번호가 건너뛸 수 있습니다. `default.log`는 이 순서대로 증가합니다.
같은 기록이 상세 파일과 LLM 파일 양쪽에 해당하면 통합 로그에도 두 행으로 남습니다. `log` 필드로 어느 파일의 기록인지 구분합니다.

기록은 실제 작업 시 생성합니다. 종료되지 않은 호출을 성공으로 보충하거나 과거 결과로 채우지 않습니다.

## 산출물과 같은 단계 경로

단계 기록은 `test-0001/02-calculation/<기능>/detail.log`처럼 런 산출물의 문항·단계·기능 경로를 따릅니다. 원응답 등 파일 저장 이벤트는 그 파일의 실제 디렉터리에 해당하는 로그 경로로 연결됩니다. 각 JSON 행의 `artifact_directory`와 `log_path`로 결과 폴더와 로그 폴더를 대응시킵니다. 전체 기록은 루트 `default.log`에서 시간순으로 읽습니다. CLI 인자는 공통 `log/cli.log`에도 기록합니다.

Timestamp values use the system local time with milliseconds and a UTC offset (YYYY-MM-DD HH:mm:ss.SSS+09:00 on a Korean system). Existing raw records are preserved.

## 전체 명령과 소요 시간

`execution.run`과 `execution.round`의 START/END에는 실제 argv·시스템 현지 시작/종료 시각·단조 시계로 측정한 소요 시간이 남습니다. `execution.timing_summary`는 전체 경과 시간과 LLM 사용량 요약입니다. `production.continue_feedback`는 같은 실행의 차수 이어 실행 명령입니다. 모두 공통 `log/cli.log`와 해당 실행 `default.log`에서 검색할 수 있습니다.
