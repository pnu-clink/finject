# A02 응답 근거 검토 — 설계와 확인 기록

2026-10-03 사용자 요구에 따라 최신 실험 뷰어와 A02·A03의 현재 저장 계약을 확인하고, 원본 제외 응답의 설명·evidence·답변 결정에 대한 검토 설계를 기록했습니다. **요구사항과 설계 문서이며, 새로운 의미 판정 결과는 없습니다.**

## 읽는 순서

1. [응답 근거 검토 설계](../../../docs/02-experiments/02_analysis/02_comparison/02-response-grounding-review.md): 현재 부족한 부분, 판정 항목, 유형별 분모, 뷰어와 A03 사용 계약.
2. [A02 관계 비교](../../../docs/02-experiments/02_analysis/02_comparison/README.md) → [A03 연구 해석](../../../docs/02-experiments/02_analysis/03_research/README.md): 현행 구현과 추가 요구의 구분.
3. [확인한 소스와 상태](design-review.json) → [검사 기록](validation.json) → [작업 로그](events.jsonl).

[기존 통합 문서 뷰어에서 보기](http://127.0.0.1:8893/?run=20261003-analysis-response-grounding-design&doc=docs%2F02-experiments%2F02_analysis%2F02_comparison%2F02-response-grounding-review.md)

현재 확인에서는 문서 API가 본문을 반환하지만 화면이 최신 데이터셋으로 이동하는 문제가 있습니다. `[viewer-experiments]`에 수정을 전달했습니다. 표시 확인 상태는 `validation.json`을 기준으로 보며, 수정 전에는 위 읽는 순서의 설계 문서 파일을 직접 확인해 주세요.

## 파일 역할

|파일|역할|
|---|---|
|`design-review.json`|읽은 현재 소스·해시·확인 사실, 요구 반영 범위와 미구현 항목|
|`validation.json`|문서 연결·README 템플릿·소스 보존·뷰어 확인 범위|
|`events.jsonl`|이 작업의 변경·확인·전달 이력|
|`documentation.json`, `summary.json`|기존 통합 뷰어가 읽는 문서 색인과 설계 상태|
|`migration.json`|문서 뷰어의 공통 형식. 이번 작업의 이관 대상은 없어 빈 목록|

README는 `src/finarch/documentation/templates/research/analysis-response-grounding-design-readme.md`에서 생성합니다. 별도 뷰어 HTML을 만들지 않습니다. 현재 실험 코드·풀이 프롬프트·응답 스키마·기존 실험 산출물은 변경하지 않으며, 모델 호출·중지 해제는 수행하지 않습니다. 문서 검사는 의미 판정 실행이나 사용자 검토 완료를 뜻하지 않습니다.
