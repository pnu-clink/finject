# Preparation 보완 1회와 Generation 재개

`plan.json`은 대상·모델·추가 호출 상한입니다. `01-original`에 기존 실패 문항 전체와 배치 집계·승인 입력 목록을 보존합니다. 기존 실패를 성공으로 덮어쓴 기록이 아닙니다.

현재 문항 폴더의 `repair-provenance.json`에서 이전 시도 위치와 모든 파일 해시를 확인합니다. 원문 검사 실패는 문장 보완 후 재검사하고, 기존 검사 통과 문항은 해당 검사를 재사용해 POT를 한 번 다시 생성합니다. 생성에 실패 원인 지침을 추가하며, 감사 판정 기준은 유지합니다. 여전히 근거가 불명확하거나 계산·그래프 검사가 실패하면 승인하지 않습니다.

`results.json`은 보완 결과입니다. 통과 문항을 승인한 뒤 Generation의 완료 유형은 유지하고, 미완료 유형과 새로 승인된 문항을 이어서 처리합니다. 최종 사람 검토는 실행하지 않습니다. 뷰어에서 같은 실행의 현재 문항을 선택하면 보완 후 단계와 판정을 확인할 수 있습니다. 시간과 호출 원응답은 각 처리 폴더에 남습니다.

## 병렬 처리 기록
Preparation은 config.json의 parallelism.preparation(최대 10), Generation은 parallelism.generation(최대 2)로 문항 수를 제한합니다. Generation 선행 다섯 유형 후 Source 두 유형을 실행하며 Source 종료까지 문항 자리를 유지합니다. VALUE 앞·뒤는 동일한 추가 문장을 공유합니다. queue.json에서 현재 상태, queue.jsonl에서 변경 이력, progress.json 및 각 유형 run.json에서 결과를 읽으세요. 뷰어의 차수 요약 위에 대기열 상태가 표시됩니다.
