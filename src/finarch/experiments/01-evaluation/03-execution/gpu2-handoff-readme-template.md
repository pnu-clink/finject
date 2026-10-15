# GPU-2 · FinanceReasoning 1,080문항 실험 인계

실행 ID: **$run_id**. 준비 시각: $created_at. 이 폴더는 원격 실험에 전달할 자료입니다. 로컬에서 vLLM을 실행했다는 뜻이 아닙니다. 현재 상태는 [state.json](state.json)과 [인계 로그](events.jsonl)를 확인하세요.

읽는 순서:

1. [위임 범위와 실행·취합 기준](PLAN.md)
2. [입력·Luna 동일성 검증](verification.json)
3. [모델·GPU·탐색 후보 설정](config.json)
4. [선정·전달 로그](events.jsonl), [원격 전달용 파일 해시](manifest.json): 문항 연결은 원천 run의 모델별 요청 manifest에서 읽어 위 실행 조건 목록에 담습니다.

| 파일 | 역할 |
|---|---|
| `00-definition/` | exp-006에서 바이트 그대로 복사한 영어 프롬프트·V4 응답 스키마 |
| `01-input/public.jsonl` | 동결한 1,080원문·7,560변형의 Q/C. 이전 원응답을 포함하지 않음 |
| `01-input/model-inputs.jsonl` | 모델에 보낼 Q/C와 `answer_format.decimal_places`만 담은 input |
| `01-input/private.jsonl` | 정답·부호·제작 출처. 모델 요청에 넣지 않고 평가에만 사용 |
| `01-input/trial-matrix.jsonl` | 두 추론 조건 기준 32,400조건 목록. 토글 미지원 모델은 해당 축을 제거하고 별도 분모 확정 |
| `provenance/` | 과거 입력·정의 해시, 현재 제작본과 차이, 모델 호출 없는 검증 기록 |
| `support/legacy-source-snapshot.json` | 기존 검사·집계·폴더 코드의 읽기 전용 사본. 원격 신규 구현으로 표현하지 않음 |
| `support/exporter-source.txt` | 전송 파일을 표준 Python으로 검사할 수 있는 프로그램 소스 사본 |

**요청 수:** 추론 두 조건이면 원문 $originals × 2 = 2,160, 변형 $variants × P0/P1 × 2 = 30,240, 모델당 **32,400건**입니다. 한 조건이면 **16,200건**입니다. 배치 탐색·웜업·반복검증 호출은 본실험과 분리합니다. 정확한 전체 합계는 원격의 모델별 지원 조건표에서 확정합니다.

목적은 **GPU 4장에서 전체 실험을 얼마나 빨리 마칠 수 있는지 실측**하는 것입니다. 사전 탐색 후보를 전역 최적이라고 부르지 않습니다. 로딩·탐색·본실험 시간을 각각 기록하고, 실제 측정 전에는 소요 시간이나 GPU 비용을 만들어 넣지 않습니다.

기존 exp-006 앞 100문항과 이번 자료의 해당 800개 Q/C·정답·형식 메타데이터는 동일합니다. 전체 1,080개는 당시 동결한 exp-002 입력을 사용합니다. 최신 제작본과 8,640개 Q/C가 모두 같지만 EA 라벨 정리 후 새로 계산하는 item_id는 다르므로 기존 ID를 보존합니다. [차이 기록](provenance/current-vs-frozen.json)을 확인하세요. 과거 응답은 실험 입력 또는 결과로 재사용하지 않습니다.

주관 작업: **vllm gpu-2에서 Qwen3.8 27B 구동**. 원격 메인 작업이 서버 구성·탐색·본실험·실패 분석과 최종 취합을 담당합니다. 로컬은 자료 전송·무결성 확인을 담당합니다. 고정 루트는 `reports/experiments-run`; 기존 실험 뷰어에서 이 폴더의 Markdown 문서를 읽습니다.
