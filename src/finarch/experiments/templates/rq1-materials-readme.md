# RQ1 분석자료 — {run_id}

1. `summary.json`: 모델·데이터 출처·풀이·추론·변형별 사분면과 전체 분모.
2. `records.jsonl`: 각 점의 원본/변형 요청 ID, 저장 응답 경로, 입력 해시.
3. `source-selection.jsonl`: OVS 포함·제외·미확정 및 실제 IC-value 부모 연결.

OV/OR/OE는 원본의 저장 수치 일치 × 해당 분류 제출이며 분자는 두 축 모두 참인 건수입니다. OVS/OVS_all 분자는 IC-source의 CONFLICT 제출 건수입니다. ANSWERABLE 제출 비율도 별도 기록합니다. OVS의 m은 해당 source 유형과 연결된 OV 양쪽 성공 집단으로 한정합니다. 잘못된 source 부모 연결을 이름으로 추측하지 않습니다.

CONFLICT/INSUFFICIENT_EVIDENCE 제출은 의미적 감지 성공이나 문항 답변 불가능성의 확정이 아닙니다. 근거 타당성은 기존 A02에서 별도로 읽습니다. Unguided의 분류 미요구, 미수집, 형식 실패는 미배치로 남기고 전체 분모에서 삭제하지 않습니다. 분모 0은 계산 불가입니다. 3-1 역산은 TBD입니다.

생성: `PYTHONPATH=src .venv/bin/python -m finarch.experiments.pipeline rq1-materials --run reports/experiments-run/{run_id}`. 저장 응답만 읽고 모델을 호출하지 않습니다. 생성 이력은 실행 폴더의 기존 이벤트 로그에 기록합니다. 화면은 공통 experiments viewer의 02 Analysis A01 상단에서 읽도록 연결합니다.
