# FInject 실험·평가와 리뷰 개선 방향 안내

2026-09-28 · 실험·평가와 사용자가 제공한 실제 리뷰 4건, 개선 우선순위를 함께 읽는 자료입니다. 원논문 보고값·가상 계산·리뷰어 의견·현재 fin-arch 조건·연구 제안을 구분합니다.

## 읽는 순서

1. [실험·평가와 리뷰 정리본](RESEARCH-DIRECTION.md): 실험 대상 → 지표 → 가상 계산 → 원논문 결과 → 실제 리뷰 4건 → 개선 우선순위. 공통 화면이 이 파일을 직접 읽습니다.
2. [원논문 전체 모델 결과표 해설](../20260926-finject-section-guide/chapters/06-experiments.md), [과제·지표 상세 해설](../20260926-finject-section-guide/chapters/05-tasks-metrics.md): 지표와 결과를 더 깊게 읽을 때 확인합니다.
3. [현행 데이터셋 문서](../../../docs/01-dataset/README.md), [현행 실험 문서](../../../docs/02-experiments/README.md): 현재 프로젝트 작업 기준입니다.

[공통 연구 뷰어](http://127.0.0.1:8896/viewer/research/)에서 **2026-09-28 · FInject 실험·평가와 실제 리뷰 4건**을 선택하시면 실제 정리본을 읽습니다. 서버가 꺼져 있으면 viewer/research/start.command를 실행합니다. 결과 폴더에 별도 HTML을 만들지 않습니다.

## 근거와 파일 역할

|파일|역할|
|---|---|
|[RESEARCH-DIRECTION.md](RESEARCH-DIRECTION.md)|정리본의 단일 원본. 공통 뷰어가 직접 읽습니다.|
|[sources.json](sources.json)|확인한 원전·현행 문서의 경로, SHA-256, 용도와 대조 범위|
|[events.jsonl](events.jsonl)|작성·문서 갱신·자료 확인·화면 확인 기록|
|[verification.json](verification.json)|원문 보존·템플릿·산술·출처·화면의 실제 확인 상태|

정리본의 S1은 로컬 원논문 PDF입니다. 경로는 sources.json의 PRIMARY_ORIGINAL_PDF 항목에 보존했습니다. 파일명은 `2026_CIKM_FinanceBench (10).pdf`이며 5쪽입니다.

S5는 사용자가 제공한 Review 1–4 코멘트 원문입니다. 첨부 파일의 실제 경로·해시는 sources.json의 `USER_SUPPLIED_REVIEW_TEXT` 항목에 보존했습니다. 이전 내부 R1–R6 요약은 리뷰 원문으로 인용하지 않습니다. 리뷰 4건의 권고와 최종 채택 결정은 다른 정보이며, 메타리뷰·최종 결정문은 첨부 파일에서 확인되지 않습니다.

- S2: [현행 7개 변형 조건](../../../docs/01-dataset/02-generation/01-perturbation/01-variant-rules.md)
- S3: [현행 실험 파이프라인](../../../docs/02-experiments/README.md)
- S4: [현행 데이터셋 파이프라인](../../../docs/01-dataset/README.md)

## 확인 범위

원논문 PDF와 사용자 제공 리뷰 원문을 대조한 문헌 정리입니다. 새 실험·별도 모델 호출·원자료 재채점은 0회이며, 원논문 데이터의 전수 검증이나 결과 재현을 뜻하지 않습니다. 현재 실험의 완료 수·성능 수치는 이 자료에서 새로 주장하지 않습니다. 출판·채택·온라인 공개 현황은 이번 확인 범위에 포함하지 않았습니다.

README는 src/finarch/documentation/templates/research/finject-quick-guide-readme.md에서 documentation/manage.py refresh로 생성합니다. 자료·화면 확인과 사용자 검토 완료를 구별하며, 사용자 검토 상태는 미확인입니다.
