# 04 Quadrant — 연구 발견 정리

[Analysis 소스](../README.md) · [상세 흐름](../../../../../docs/02-experiments/02_analysis/04_quadrant/README.md)

run 대응: `02_analysis/04_quadrant`.

|파일|입구|입력 → 처리 → 출력|
|---|---|---|
|[pipeline.py](pipeline.py)|`prepare / finding_step / run`|완료 A03 → F 전용 요청·설정된 Analysis backend 호출·검사·등록 스텝 순차 진행 → manifest·calls·D01 summary·state|
|[01-findings/grouping.py](01-findings/grouping.py)|`trace / model_input / validate / collect`|F·인용 관찰·실제 응답 → 조건 계보 확인·F만 모델 전달·전체 대응과 정확 인용 검사 → 원래 F를 보존한 그룹·네 조건 색인|

프롬프트는 [experiments/prompts](../../prompts/02-analysis.04-quadrant.findings.md), 응답 형식은 [experiments/schemas](../../schemas/json/02-analysis.04-quadrant.findings.response.schema.json)에 둡니다. 상위 `pipeline analysis-postprocess --run <run>`은 A04만, `analysis --run <run>`은 A01 → A02 → A03 → A04를 진행합니다. 모델·effort·동시 한도는 같은 run의 설정을 사용하며 별도 모델 파일을 만들지 않습니다.

개선 토의 안건·관찰은 그룹 대상에서 제외합니다. 관찰은 F가 인용한 실제 응답 조건을 찾아주는 계보로만 사용합니다. 여러 조건의 비교 발견은 공동 근거로 표시하며 조건 효과로 단정하지 않습니다.
