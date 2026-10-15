# FinanceReasoning 제작 실패 원인과 개선안

분석 기준: `{source_run}` · 저장된 최종 결과와 당시 요청·응답을 읽은 분석입니다. 모델 호출과 데이터 제작 재실행은 없습니다.

읽는 순서: **공통 뷰어의 Preparation→Generation 문항 흐름 → 758문항의 유형별 결과 → 구간별 표와 발생 type → 접힌 세부내역 → 원인별 목록과 문항별 원문·근거**입니다. 1,664 실패와 3 미평가는 문항 수가 아니라 758문항×7유형에서 나온 결과 수입니다. 표의 P02–P05, G01–G03은 최종 중단 위치이며, 수리할 파일이나 원문의 오류가 확정된 위치를 뜻하지 않습니다. Generation type 표시명은 실행 순서대로 `IC-v1`, `IC-v2`, `IC-s1`, `IC-s2`, `IC-r`, `EA-v1`, `EA-v2`입니다. 저장된 제작 type 코드는 그대로 둡니다.

- `REPORT.md`: 문항 수와 문항×type 결과 수의 관계, 실행 순서의 구간별 표, Generation 행의 발생 type별 건수와 원인 설명, 원본 보완 여부, 처리 방식 개선안, 대표 사례. 공통 뷰어에서 표 아래의 `Preparation 세부내역`, `Generation 세부내역`, `종합 세부내역`을 펼쳐 읽습니다.
- `failure-review.json`: Preparation 212문항과 Generation 실패·미평가 1,667유형의 분류 및 근거 연결. Generation 대상 원문은 758개입니다.
- `manifest.json`: 실제 읽은 근거 파일의 경로와 SHA-256. 원기록은 수정하지 않습니다.
- `analysis-log.jsonl`: 집계·분류·산출 기록.
- `presentation-validation.json`: 단계별 문항·type 결과의 합계, 구간별 표의 순서·합계, 접기 영역의 화면 확인 기록.
- `viewer-validation.json`: 실제 화면의 분류·검색·근거 열람과 근거 파일 해시 확인 결과.
- `validation.json`: 수량, 중복, 분류 누락, 근거 파일 확인 결과.
- `summary.json`: 공통 뷰어의 실행 선택 목록에 표시할 요약.

뷰어: [원인별 보기](http://127.0.0.1:8893/?run={report_run}). 화면은 `viewer/dataset/index.html` 하나를 사용하며 선택한 실행의 실제 JSON을 읽습니다.

분류 산출 스크립트: `src/finarch/dataset/90-operations/analysis/failure_review.py`. 이 보고서의 type 표시와 건수 표시는 저장된 분류·원기록을 다시 생성하지 않습니다.

이 README는 `src/finarch/dataset/90-operations/analysis/failure-review-readme-template.md`에서 생성됩니다. 자동 검사 통과를 사람이 확인한 의미 정답으로 간주하지 않습니다. 개선안은 제안이며 수정·재실행으로 입증된 효과가 아닙니다.
