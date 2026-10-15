# 실험 프롬프트

[소스 전체](../README.md) · [응답 스키마](../schemas/json/README.md) · [E02 요청](../../../../docs/02-experiments/01_evaluation/02_request/README.md)

현행 지시 파일은 `대단계.세부단계.역할.md`로 이름 붙입니다. 파일명의 단계가 실제 요청을 만드는 단계를 가리킵니다. 모든 모델 지시는 영어 원문입니다.

|단계|읽는 파일|요청에서 하는 일|
|---|---|---|
|E02 대상 풀이|[01-evaluation.02-request.common.md](01-evaluation.02-request.common.md)|두 풀이 조건의 공통 응답 필드 안내·뒤따르는 직접 지시 적용|
|E02 일반 풀이|[01-evaluation.02-request.unguided.md](01-evaluation.02-request.unguided.md)|일반 풀이와 `classification=null` 출력 지시를 공통 지시 뒤에 결합|
|E02 기준 풀이|[01-evaluation.02-request.guided.md](01-evaluation.02-request.guided.md)|다섯 분류 중 하나를 직접 요구하는 지시를 공통 지시 뒤에 결합|
|A02 관계 해석|[shared.02-analysis.02-03.common.md](shared.02-analysis.02-03.common.md) + [02-analysis.02-comparison.response-patterns.md](02-analysis.02-comparison.response-patterns.md)|저장 응답·대응 비교를 해석|
|A03 연구 해석|[shared.02-analysis.02-03.common.md](shared.02-analysis.02-03.common.md) + [02-analysis.03-research.findings.md](02-analysis.03-research.findings.md)|A02 근거와 집계를 종합|

|A04 연구 발견 정리|[02-analysis.04-quadrant.findings.md](02-analysis.04-quadrant.findings.md)|F만 의미별 그룹화·네 풀이 조건 요약; 관찰·토의 그룹 제외|

[assets.py](../assets.py)가 이 파일을 찾고 E02 [prepare.py](../01-evaluation/02-request/prepare.py)는 새 run에 기존 실행 파일명으로 사본을 동결합니다. A02/A03/A04는 실제 결합한 지시를 모델별 요청 기록에 보존합니다. 이전 run의 동결 프롬프트와 원응답은 당시 정의로 읽습니다. 설계 후보인 `experiment/archtecture/prompts/evaluator.md`는 현재 실행 경로가 아닙니다.
