# 02-generate-text

[Step of the letter: yoga; action flow](../../../../../docs/01-dataset/02-generation/02-generate-text/README.md) · [A whole source structure](../../../../../docs/01-dataset/90-operations/05-source-layout.md)

This folder owns the execution code for the documented stage. Output paths follow the existing run contract.

|File|Role|
|---|---|
|[dtt_realize.py](dtt_realize.py)|Stage internal processing and inspection|
|[prompt_rerun.py](prompt_rerun.py)|PR01–04: new Stage16/17 run from immutable validated inputs and plans.|
|[realization_prompts.py](realization_prompts.py)|R16P: common serialization contract plus exactly one perturbation objective.|
|[stage.py](stage.py)|Ordered stage subjobs; artifact paths retain their existing contract.|
|[text_preview.py](text_preview.py)|Stage internal processing and inspection|
