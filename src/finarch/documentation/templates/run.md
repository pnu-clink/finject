# 데이터셋 문서 재정리

작업일: 2026-09-23. 이 기록은 문서 취합·이관과 뷰어 연결입니다. 제작·실험 배치와 모델 호출은 실행하지 않았습니다.

## 읽는 순서

1. [전체 문서](../../../docs/README.md) → [데이터셋 파이프라인](../../../docs/01-dataset/README.md)
2. 입력 → Preparation → Generation → 결과 전달의 각 README와 단계 문서
3. [요구·구현 차이](../../../docs/01-dataset/99-open-issues.md)
4. [기존 문서 이관표](../../../archive/20260923-documentation-reorganization/MIGRATION.md)

## 파일 역할

|파일|역할|
|---|---|
|documentation.json|공통 뷰어가 읽는 현재 문서·보관 원본 색인|
|migration.json|모든 기존 docs 파일의 원본 해시·보관 위치·새 소속|
|source-inventory.json|기존 문서의 제목·절·요구 관련 문장 및 소속. 추출 결과를 자동으로 새 요구로 채택하지 않음|
|requirements-map.json|기존 R01~R35 요구의 새 소속과 대체·보류 적용 범위|
|run-layout-reference.json|채번 대조에 사용한 실제 run 단계·세부 폴더 목록|
|validation.json|보관 원본 해시·새 링크·템플릿·색인 정합성 확인|
|events.jsonl|이번 작업의 처리 기록|
|ui-review.json|공통 뷰어에서 실제 확인한 항목과 한계|

## 확인 화면

공통 뷰어에서 실행 `20260923-dataset-documentation`을 선택합니다. 단일 화면이 색인에 연결된 실제 최신 문서를 읽으며 결과 폴더에 별도 HTML을 만들지 않습니다. 브라우저 검토 결과는 ui-review.json을 확인합니다. 파일 저장·자동 검사 통과를 사용자 검토 완료로 표시하지 않습니다.

기존 파일은 [보관 안내](../../../archive/20260923-documentation-reorganization/README.md)에 원본 그대로 보존했습니다. 과거 자료의 상대 링크는 당시 원래 경로 기준이며 문서 뷰어가 이관표로 해석합니다. archive Markdown을 편집해 원본 해시를 바꾸지 않습니다.

[요구사항 대응표](requirements-map.json) · [채번 기준 run 구조](run-layout-reference.json) · [문서 무결성 결과](validation.json)
