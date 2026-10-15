# Generation 단계별 기록

`01-perturbation` 그래프 변경·계산 확인 → `02-generate-text` 실제 요청·응답·편집 검사 → `03-validation` 고정 의미 검사 → `04-human-review` 최종 사람 검토 순서입니다.

실패한 유형과 변경된 의존 유형만 다음 차수에 재시도합니다. 이전 차수의 통과 기록은 출처를 유지합니다. IC-SOURCE Type 1은 검증된 IC-VALUE 앞, Type 2는 뒤를 사용합니다. IC-VALUE 앞·뒤는 같은 생성 문장을 배치한 조건 쌍입니다.

보완 지침은 각 차수의 `문항/유형/feedback`에 따로 저장하고 다음 차수의 같은 문항·유형 생성 호출에만 추가합니다. `00-evidence.json`은 실패 근거, `02-result.json`은 보완 내용, 다음 차수의 `feedback/01-applied.json`은 실제 적용 출처와 해시입니다. 검사 프롬프트는 재시도 중 변경하지 않습니다. `final-validator.json`은 재시도 여부와 원인을 기록합니다. 자동 통과는 사람 승인이 아닙니다.

공통 뷰어에서 런·차수·문항·유형·단계를 선택하면 실제 저장된 파일을 읽습니다. 빈 단계는 미실행입니다. 실행 명령·시작과 종료·소요 시간은 timing.json 및 같은 구조의 로그에 남습니다.

QI01 정책은 기본 off입니다. 새 실행에서 `ea_recovery_policy.enabled=true`이면 계획의 `recovery_preview`와 최종 본문의 `03-validation/05-recovery-screen.json`을 함께 읽습니다. 최종 파일에는 검사 본문 해시·대상 식별 정보·복원식·인용 위치가 있습니다. RECOVERABLE/UNKNOWN은 별도 Python 품질 gate를 막고 LLM handler 재시도를 하지 않습니다. audit v3의 기존 PASS와 전체 EA 미평가는 보존합니다. 현재 두 등록 grammar 이외의 관계는 UNKNOWN이며, 대상 재선정은 아직 하지 않습니다. 결과 파일 트리에서 sidecar를 읽을 수 있으며 별도 뷰어 화면을 만들지 않습니다.

## 병렬 처리 기록
Preparation은 config.json의 parallelism.preparation(최대 10), Generation은 parallelism.generation(최대 2)로 문항 수를 제한합니다. Generation 선행 다섯 유형 후 Source 두 유형을 실행하며 Source 종료까지 문항 자리를 유지합니다. VALUE 앞·뒤는 동일한 추가 문장을 공유합니다. queue.json에서 현재 상태, queue.jsonl에서 변경 이력, progress.json 및 각 유형 run.json에서 결과를 읽으세요. 뷰어의 차수 요약 위에 대기열 상태가 표시됩니다.

문항·유형별 피드백 생성은 parallelism.feedback(최대 3)으로 병렬 처리합니다. 같은 문항·유형의 중복 입력은 거절하고 완료된 피드백은 재사용합니다. Generation 문항 병렬 상한 2는 유지합니다.
