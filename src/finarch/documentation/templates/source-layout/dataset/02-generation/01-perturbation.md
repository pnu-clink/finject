# 01-perturbation

[문서의 단계·요구·실행 흐름](../../../../../docs/01-dataset/02-generation/01-perturbation/README.md) · [전체 소스 구조](../../../../../docs/01-dataset/90-operations/05-source-layout.md)

이 폴더는 위 문서 단계의 실행 코드를 소유합니다. 결과의 물리 경로는 기존 run 계약을 따릅니다.

|파일|역할|
|---|---|
|[ea_inversion.py](ea_inversion.py)|Exact bounded inversion of existing graph equations with surviving Q/C bindings.|
|[ea_plan.py](ea_plan.py)|단계 내부 처리·검사|
|[generation_plan.py](generation_plan.py)|Build graph branches and edit contracts from approved preparation data.|
|[hyperparameters.py](hyperparameters.py)|Validate batch controls and snapshot selected provider profiles before calls.|
|[production_plan.py](production_plan.py)|단계 내부 처리·검사|
|[relation_plan.py](relation_plan.py)|등록 숫자 규칙으로 양쪽 금액을 비교하고 원본을 보존한 관계 계산 분기를 생성합니다.|
|[relation_scope.py](relation_scope.py)|표의 날짜·설명 제외, 숫자 규칙 적용, 기간·부분/전체 검사·관계 계약; 표 전체 뒤 삽입 좌표를 제공합니다.|
|[source_from_value.py](source_from_value.py)|Build attribution-only requests from the current run's assigned audited IC-VALUE variant.|
|[source_plan.py](source_plan.py)|단계 내부 처리·검사|
|[stage.py](stage.py)|Ordered stage subjobs; artifact paths retain their existing contract.|
|[value_plan.py](value_plan.py)|단계 내부 처리·검사|
|[value_positions.py](value_positions.py)|단계 내부 처리·검사|
