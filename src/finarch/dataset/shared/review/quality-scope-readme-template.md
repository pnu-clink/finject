# QI05 감사·승인 범위 보고서

원본 실행 `{source_run}`의 frozen Q/C와 현재 생성·audit 원응답·요청·당시 모델 프로필·decision/history를 읽은 새 보고서입니다. 원본을 수정하거나 문항별 사람 검토를 생성하지 않습니다. API 호출은 0회입니다.

## 결과와 읽는 순서

- 전체 {records}건 / 원문 {original_cases}건 / 고유 Q/C {unique_qc}건.
- frozen Q/C 일치 {qc_matches_frozen}, 생성 PASS {generation_pass}, 세 audit 검증축 모두 PASS {three_audit_axes_pass}건.
- `BULK_AT_USER_DIRECTION` {bulk_at_user_direction}건, 독립 문항 검토 `NOT_REVIEWED` {independent_not_reviewed}건.
- EA 전체 판정 `NOT_EVALUATED` {ea_full_not_evaluated}건. QI01 실제 반례 {qi01_counterexamples_linked}건을 관찰 본문 일치 확인 후 별도로 연결했습니다.

1. `summary.json`: 건수와 분모.
2. `quality_scope.json`: 문항별 감사 3축·승인 출처·독립 검토를 각각 확인합니다. `skip_reasons`가 있으면 `NOT_EVALUATED`입니다.
3. `manifest.json`: 실제 읽은 파일의 경로/SHA256과 읽기 완료 후 불변 확인입니다.
4. [sidecar-schema.json](sidecar-schema.json): 새 sidecar 전용 JSON Schema입니다(`src/finarch/dataset/schemas/quality_scope.py`에서 자동 export). LLM response schema가 아니며 기존 LLM 스키마·호출 registry는 바꾸지 않습니다.
5. `events.jsonl`: 시작·완료·실패 로그. `checks.txt`·`checks.json`·`viewer-check.json`이 있으면 해당 로컬 확인 결과입니다.

[공통 viewer에서 이 실행 열기](http://127.0.0.1:8893/?run={run_id}) → 품질 범위 읽기 전용 표. 보고서는 저장된 JSON만 읽고 최신 파일 변경을 다시 반영합니다. 원 생성/감사/승인 기록은 해시 검증된 읽기 전용 링크로 엽니다. QI01 결과 링크도 함께 제공하며 기존 QI01 폴더는 보존합니다. 별도 결과 HTML은 만들지 않습니다.

## 해석 제한

세 검증축은 `planned_change`(계획한 변경), `unintended_change`(의도하지 않은 변경), `readability`(가독성)입니다. 3건의 오류가 아니라 문항마다 수행한 세 판단입니다. 해당 단일 모델의 `FINAL_TEXT_ONLY` PASS는 완전한 의미 정답·EA 증명·독립 사람 검토가 아닙니다. 사용자 지시 일괄 승인도 독립 문항 검토로 바꾸지 않습니다. 과거 history의 reviewer=user만으로 실제 독립 의미 검토가 있었다고 추정하지 않습니다.

보고서의 `NOT_REVIEWED`는 선택한 근거에서 별도 독립 검토 기록을 가져오지 않았다는 뜻입니다. 이후 실제 독립 검토가 생기면 새 버전에서 별도 연결해야 합니다. 출처가 불명확한 승인 방식은 `UNKNOWN`입니다. 옛 감사·승인 기록과 새로운 QI01 반례는 별도 상태로 남습니다.

재현: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m finarch.dataset.shared.review.quality_scope --source reports/run/{source_run} --output reports/run/새-quality-run --qi01 reports/run/20260916-qi01-v1`. 기존 출력 경로 덮어쓰기는 거절하며 입력이 바뀌면 `SNAPSHOT_CHANGED`로 실패 기록을 남깁니다.
