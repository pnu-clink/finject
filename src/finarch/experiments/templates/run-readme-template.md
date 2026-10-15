# {run_id}

풀이 수집 상태: **{status}** · 원문 {originals}건 · 자동 검사 통과 변형 {variants}건. FINISHED는 풀이 수집의 종료이며 내용 분석·연구 검토 완료와 구분합니다.

`CACHE_POLICY_BLOCKED`는 캐시 차단 기능이 확인되지 않아 호출 전에 멈췄다는 뜻입니다. 계획 건수를 실제 응답 수로 읽지 마세요. `REPORT.md`와 모델별 `cache-preflight.json`에서 사유·시도 수를 확인합니다. 최신 실행 정책은 캐시 읽기·쓰기와 다른 실행의 응답 재사용을 금지하며, 이전 실행의 원기록은 당시 상태로 보존합니다. 미호출과 캐시 미사용 검증 완료는 서로 다릅니다.

`CACHE-AUDIT.md`가 있으면 이전 실행의 실제 캐시 사용량, 입력·프롬프트 동일성, 차단 원인과 미실행 대안을 먼저 읽습니다.

## 읽는 순서

1. `REPORT.md`: 모델별 실행 현황, 결과 해석, 사용량·비용.
2. `plan.json`, `config.json`: 호출 수와 고정된 설정.
3. 모델별 `01-requests/manifest.jsonl`: 문항 연결·실험 조건·풀이 입력·prompt·schema를 담은 실행 기준. 선정 순서·규칙·제외 사유·출처 확인은 `events.jsonl`의 `INPUT_SELECTION`에 기록합니다.
4. 모델별 `03-results/summary.json`, `results.jsonl`: 조건별 분모·응답·검사 결과.
5. 모델별 `calls/<문항>/<유형>/<문항>-P0-R-off.json`: 실제 요청·응답·검사·사용량을 한 파일로 읽습니다. 해당 유형의 `_records/<해시>/attempt-xxx`에 재시도별 원기록을 보존합니다.
6. `events.jsonl`, `state.json`: 재개할 때 확인할 진행 기록.
7. `layout/README.md`: 이전 폴더를 옮긴 실행의 경로 대응표·원기록 해시·검증 결과입니다.
8. Codex 모델 폴더의 `resources.jsonl`, `resources-latest.json`: 2초 간격 시스템 CPU·메모리, 동시 처리 한도, 진행 중 요청 수입니다. Codex 실행에서만 생성됩니다.
9. Native Batch 실행의 `<model>/02-batches`: 전송 파일·Batch ID·제공자 원출력·실제 사용량입니다.
10. 내용 검토를 수행한 run의 `02_analysis/01_response_review/README.md` → `02_analysis/02_comparison/summary.json`: 입력·응답의 LLM 판정, 재검토, 미평가를 포함한 비교입니다. 뷰어의 02 Analysis에서 읽습니다.

실행 당시 형식은 `00-definition/response.schema.json`과 모델별 manifest를 확인합니다. 새 입력의 `public.jsonl`에는 풀이용 Q/C와 `answer_format.decimal_places`를 함께 저장하며, LLM에게 보낼 문제 내용은 public만 읽습니다. `private.jsonl`은 정답·제작 근거를 이용한 평가 전용입니다. 요청 시 private에서 자릿수나 다른 정보를 보충하지 않습니다. 문항 ID·원문·변형·조건 연결은 모델별 요청 manifest로 통합하며 새 실행에 별도 `input-selection.json`을 만들지 않습니다. 문항 수는 요청 행 수가 아니라 manifest의 고유 item_id로 집계합니다. 최상위 `manifest.json`은 파일 해시 목록으로 용도가 다릅니다. 이전 run의 public에 자릿수가 없다면 원본을 수정하지 않고 dataset에서 새 입력을 준비해야 합니다. 과거 응답과 동결 요청은 당시 정의로 읽습니다. `00-definition`의 프롬프트·스키마·README 템플릿은 실행 당시 사본으로 보존합니다.

실험 결과 안내는 Markdown 문서로 관리합니다. 공통 `viewer/experiments`가 이 실행의 실제 저장 결과를 읽으며, 결과 폴더마다 별도 HTML을 생성하지 않습니다. 원응답·사용량·검사 기록은 JSON/JSONL로 보존합니다.

재개: `PYTHONPATH=src .venv/bin/python -m finarch.experiments.01-evaluation.pipeline run --run "{run_path}"`

한도 복구 후 재개할 때만 `--resume-limits`를 붙입니다. 실패·미실행을 정상 응답이나 유보로 계산하지 않습니다. 의미 판정은 실제 내용 검토 파일이 있는 응답만 대상으로 하며, 분석 LLM의 잠정값을 gold나 사람 승인으로 해석하지 않습니다.

3차 개발 실험의 재개·분석·논문 갱신은 `finarch.experiments.90-operations.three_rounds tick`이 담당합니다. 차수 사이 공통 입력 판정의 사용과 실제 개선 결정은 연결된 종합 기록을 읽습니다. 이전 방식의 `ANALYSIS.md`·`analysis/README.md`·`CASE-STUDIES.md`는 해당 파일이 생성된 run에만 존재합니다.

현행 V6는 부호 있는 `answer`와 `answer_meta.negative`·`answer_meta.scale`의 일관성을 검사하며 P0/P1이 같은 JSON 구조를 사용합니다. 숫자 답 없음은 유보 타당성 판정과 구분합니다. 기존 V2·V3·V4·V5 원응답은 당시 계약으로 읽고 소급 변환하지 않습니다.
