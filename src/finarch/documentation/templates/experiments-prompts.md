# The experimental prompt.

[The whole sauce](../README.md) · [Response Schema](../schemas/json/README.md) · [E02 Request](../../../../docs/02-experiments/01_evaluation/02_request/README.md)

The current instruction file is `Great. Third stage.`The name of the file is the step that you take to create the actual request.

|Stage|Read the files.|What to do on request|
|---|---|---|
|E02 The target grass.|[01-evaluation.02-request.common.md](01-evaluation.02-request.common.md)|The two-point condition of the common response field is directed; direct directed direction is applied backwards|
|E02 Common grass.|[01-evaluation.02-request.unguided.md](01-evaluation.02-request.unguided.md)|And the common grass. `classification=null` The output instructions are combined after the common instructions|
|E02 The standard grass.|[01-evaluation.02-request.guided.md](01-evaluation.02-request.guided.md)|Combine the instructions directly requiring one of the five classifications after the common instructions|
|A02 Interpretation of the relationship|[shared.02-analysis.02-03.common.md](shared.02-analysis.02-03.common.md) + [02-analysis.02-comparison.response-patterns.md](02-analysis.02-comparison.response-patterns.md)|Interpretation of the storage response-response comparison|
|A03 Research interpretation|[shared.02-analysis.02-03.common.md](shared.02-analysis.02-03.common.md) + [02-analysis.03-research.findings.md](02-analysis.03-research.findings.md)|A02 Combine the basis and the estimate|

|A04 Research findings|[02-analysis.04-quadrant.findings.md](02-analysis.04-quadrant.findings.md)|F mean by grouping; four grass conditions summary; observed; excluding the group of t|

[assets.py](../assets.py)Go and find this file.2 [prepare.py](../01-evaluation/02-request/prepare.py)A0 is the current run file name.2/A03/A04The actual combined command is stored in the model-by-model request record. The output prompt and raw response of the previous run read as defined at that time. `experiment/archtecture/prompts/evaluator.md`It's not the current runway.
