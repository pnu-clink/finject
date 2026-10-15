# 새 30건 실행

이전 10건과 원천 ID 및 Q/C가 겹치지 않는 30건입니다. 기존 100건 입력에서 원문만 선정하며 이전 코드·생성문·판정은 사용하지 않습니다. 문항 번호는 입력 묶음의 ID를 유지합니다.

원문 LLM 문장 검사를 먼저 합니다. 최대 차수는 plan.json을 따르며, hyperparameter.json을 사용하는 실행은 최초를 포함해 최대 3차까지 실패 항목만 보완·재검사합니다. 차수별 결과는 01-preparation/rounds에, 이전 원응답은 repair-history에 보존합니다. POT 불일치의 독립 계산·근거 확인은 별도이며 기존 규칙을 유지합니다. 사용자 위임에 따라 자동 검사가 통과한 Preparation만 승인하고 실패는 사유와 함께 제외합니다. 최종 Generation 사람 검토는 하지 않습니다.

`selection-evidence.json` → `01-preparation` → `02-generation/RESULTS.md` 순서로 읽습니다. `execution-progress.json`은 실행 프로세스의 현재 단계와 처리 수를 표시하며, heartbeat는 모델 응답 완료를 뜻하지 않습니다. 공통 뷰어에서 이 런을 선택하십시오.

## 병렬 처리 기록
Preparation은 config.json의 parallelism.preparation(최대 10), Generation은 parallelism.generation(최대 2)로 문항 수를 제한합니다. Generation 선행 다섯 유형 후 Source 두 유형을 실행하며 Source 종료까지 문항 자리를 유지합니다. VALUE 앞·뒤는 동일한 추가 문장을 공유합니다. queue.json에서 현재 상태, queue.jsonl에서 변경 이력, progress.json 및 각 유형 run.json에서 결과를 읽으세요. 뷰어의 차수 요약 위에 대기열 상태가 표시됩니다.
