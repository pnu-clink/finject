# Dataset — 입력부터 제작 결과 전달까지

[전체 소스 구조](../../../docs/01-dataset/90-operations/05-source-layout.md) · [문서 파이프라인](../../../docs/01-dataset/README.md)

|순서|폴더|책임|
|---|---|---|
|00|[00-input](00-input/README.md)|원천 선정·정규화·Q/C/A|
|01|[01-preparation](01-preparation/README.md)|원문·검토·Python 풀이·그래프·검증·검토 자료|
|02|[02-generation](02-generation/README.md)|변형 계획·문장 생성·검증·오류 처리·검토 자료|
|03|[03-release](03-release/README.md)|공개 입력·기준선·출처 짝 검토, 출판은 설계 상태|
|공통|[90-operations](90-operations/README.md)|차수·스케줄·gate·실패·피드백 기록|
|화면|[viewer](viewer/README.md)|저장된 제작 자료 조회·HTML 조립|

`shared`는 제작 단계 공통 계산·감사, `prompts`와 `schemas`는 제작 호출 계약, `checks`는 오프라인 검사입니다. 대상 모델 실험 코드는 인접한 `experiments`에 둡니다.
