# A100 생성 데이터 평가와 로컬 분석

상태와 실행 순서는 `evaluation-plan.json`, 서버 진행은 `remote-queue-state.json`(회수 시점 표시), 회수·로컬 분석은 `recovery-state.json`을 읽습니다. 준비·전송 검증은 평가 완료가 아닙니다.

- 데이터: TAT-QA 원문 291건, FinanceReasoning 원문 1,260건. 각 원문과 7변형에 Unguided/Guided × reasoning OFF/ON을 적용합니다.
- 순서: Qwen3-8B 두 데이터셋 → Qwen3-14B 두 데이터셋 → Qwen3.8-27B 두 데이터셋.
- 총 요청: 148,896건. 외부 평가 API 과금 0, GPU 인프라 비용은 미확인입니다.
- 각 모델의 정확한 revision, 실행 ID, 개수는 `evaluation-plan.json`에 기록합니다.
- 원격 루트: `/home/clink-wooix/workspace/finarch/experiments`. data/generated, src/finarch, config/experiments, reports/experiments-run 구조를 유지합니다.

읽는 순서:

1. `transfer-manifest.json`·`archive-sha256.json`·`transfer-receipt.json`: 최초 1,070파일 전송과 해시 검증. 추가 실행 모듈·요청의 해시는 서버 `sync-release.json`·실행별 `sync-input.json`·`manifest.json`이 기준입니다.
2. `evaluation-plan.json`: 6개 실행의 고정 순서와 요청 수.
3. 각 실행 `00_input/selection.json`: 선정·제외 이유와 분석 메타 누락. `public.jsonl`과 `private.jsonl`은 item_id로 연결하며 모델에는 question/context/answer_format만 전달합니다.
4. 서버 `preflight.log`, 각 실행 `01_evaluation/01_preparation/token-preflight.json`: 실제 모델 토크나이저로 모든 입력+출력 한도 검사. 잘라 넣지 않습니다.
5. 서버 `queue-state.json`, 실행별 `server.log`, `01_evaluation/03_execution/<model>/remote-state.json`: 서버 시작·진행·실패.
6. 각 요청 `remote-results/<trial_id>/provider-request.json`, `raw-response.json`, `delivery.json`, `format-check.json`: 실제 요청·원응답·사용량·종료 이유·형식 검사. 미확인 전송은 자동 재시도하지 않습니다.
7. 서버 `recovery/<run>.ready.json`, 로컬 `recovery-manifest.json`: 봉인 압축 SHA와 전 파일 해시. 기존 파일의 다른 내용 덮어쓰기를 거부합니다.
8. 로컬 E04의 숫자 비교와 `02_analysis`: 기존 실험 뷰어에서 원문·응답을 확인하고 분석 결과를 읽습니다.

기본 런타임은 TP4, bfloat16, 동시 요청 16, max_num_seqs 32, batched tokens 8,192, context 40,960, 최대 출력 8,192입니다. 이는 최적화 결과가 아닌 초기 설정입니다. reasoning 포함 출력 한도에 걸린 응답을 성공으로 숨기지 않고 원응답/finish_reason으로 보존합니다. cache는 새 평가 서버에서 끄고 실행 전후 prefix cache hit 0을 검사합니다. 실패·미수집·형식 오류를 제외하여 분모를 줄이지 않습니다.

합본의 후보값·제작 검사 범위 등 일부 보조 메타가 없는 것은 전송 누락과 다릅니다. `selection.json.analysis_metadata_gaps`에 보존합니다. Q/C와 응답 근거 판정은 진행할 수 있지만 자료가 없는 후보 A/B 비교 등을 완전한 분석으로 주장하지 않습니다. 해시 일치·형식 통과는 의미 정답이나 분석 타당성의 보장이 아닙니다.
