# The JSON scheme

[The whole sauce](../../README.md) · [Prompts](../../prompts/README.md) · [colored](index.json)

The file name. `Great. The third stage.`. `index.json` `schema_id`The file name is `.schema.json`It's a matching value. Only the response format that matches the prompt is sent to the model, and the storage record format is not sent to the models.

|Stage|File|Purpose|
|---|---|---|
|E02|[01-evaluation.02-request.solver.response.schema.json](01-evaluation.02-request.solver.response.schema.json)|Common Standard Frequency Shared by FinancialAnswerV7 Response|
|A02|[02-analysis.02-comparison.response.schema.json](02-analysis.02-comparison.response.schema.json)|The analytical model returns the observed response|
|A02 The record.|[02-analysis.02-comparison.interpretations.schema.json](02-analysis.02-comparison.interpretations.schema.json)|Structural analysis of the stored interpretation array|
|A03|[02-analysis.03-research.findings.response.schema.json](02-analysis.03-research.findings.response.schema.json)|Analysis model returns the study findings|

|A04|[02-analysis.04-quadrant.findings.response.schema.json](02-analysis.04-quadrant.findings.response.schema.json)|F is the whole group correspondence: four conditions summary: exact citation|

[assets.py](../../assets.py)Come on [contracts.py](../../02-analysis/contracts.py)It reads the current file, and when it runs, it sends the prompt and the response schema together, and it saves the actual transmissions to the run, not mixing the schema of the previous run with the current file. `experiment/archtecture/schemas/public-input.schema.json`·`evaluator-response.schema.json`It's not a design candidate, and it's not the response scheme for the current target model request.
