# 실험 JSON 스키마

[소스 전체](../../README.md) · [프롬프트](../../prompts/README.md) · [색인](index.json)

파일명은 `대단계.세부단계.용도.schema.json`입니다. `index.json`의 `schema_id`는 파일명에서 `.schema.json`을 뺀 값입니다. 프롬프트와 짝을 이루는 응답 형식만 모델에 보내며, 저장 기록 전용 형식은 모델에 보내지 않습니다.

|단계|파일|용도|
|---|---|---|
|E02|[01-evaluation.02-request.solver.response.schema.json](01-evaluation.02-request.solver.response.schema.json)|일반·기준 풀이가 공유하는 FinancialAnswerV7 응답|
|A02|[02-analysis.02-comparison.response.schema.json](02-analysis.02-comparison.response.schema.json)|분석 모델이 반환하는 관찰 응답|
|A02 기록|[02-analysis.02-comparison.interpretations.schema.json](02-analysis.02-comparison.interpretations.schema.json)|저장된 해석 배열의 구조 검사|
|A03|[02-analysis.03-research.findings.response.schema.json](02-analysis.03-research.findings.response.schema.json)|분석 모델이 반환하는 연구 발견 응답|

|A04|[02-analysis.04-quadrant.findings.response.schema.json](02-analysis.04-quadrant.findings.response.schema.json)|F 전체 그룹 대응·네 조건 요약·정확 인용|

[assets.py](../../assets.py)와 [contracts.py](../../02-analysis/contracts.py)가 현재 파일을 읽습니다. 실행할 때는 프롬프트와 응답 스키마를 함께 전달하고 실제 전송본을 run에 보존합니다. 과거 run의 schema와 현재 파일을 혼합하지 않습니다. `experiment/archtecture/schemas/public-input.schema.json`·`evaluator-response.schema.json`은 별도 설계 후보이며 현재 대상 모델 요청의 응답 스키마가 아닙니다.
