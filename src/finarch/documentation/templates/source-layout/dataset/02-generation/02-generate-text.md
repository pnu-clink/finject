# 02-generate-text

[문서의 단계·요구·실행 흐름](../../../../../docs/01-dataset/02-generation/02-generate-text/README.md) · [전체 소스 구조](../../../../../docs/01-dataset/90-operations/05-source-layout.md)

이 폴더는 위 문서 단계의 실행 코드를 소유합니다. 결과의 물리 경로는 기존 run 계약을 따릅니다.

|파일|역할|
|---|---|
|[dtt_realize.py](dtt_realize.py)|단계 내부 처리·검사|
|[prompt_rerun.py](prompt_rerun.py)|PR01–04: new Stage16/17 run from immutable validated inputs and plans.|
|[realization_prompts.py](realization_prompts.py)|R16P: common serialization contract plus exactly one perturbation objective.|
|[stage.py](stage.py)|Ordered stage subjobs; artifact paths retain their existing contract.|
|[text_preview.py](text_preview.py)|단계 내부 처리·검사|
