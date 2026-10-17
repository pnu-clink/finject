# Experimental storage and operation

[Step of the letter: yoga; action flow](../../../../docs/02-experiments/README.md) · [A whole source structure](../../../../docs/01-dataset/90-operations/05-source-layout.md)

This folder owns the execution code for the documented stage. Output paths follow the existing run contract.

|File|Role|
|---|---|
|[label_migration.py](label_migration.py)|Reconcile the delegated EA metadata rename against its original backup.|
|[storage.py](storage.py)|Atomic storage, fusion, and storage. `configuration`It checks the run ID and reads the cache-exceptions.json model approval separately. It records the actual Python command and step; batch name; action event to events.jsonl and pipeline.log.|
|[settings.py](settings.py)|Interpret the schedule/run of the default hyperparameter.json and the common codex-profiles.toml to fix the run settings. 3.8 Flash and the 3.5 Flash-Lite blocks the OFF of reasoning. 3.8It's low/medium/high, 3.5 Lite only prepares the ON level specified in the minimum/low/medium/high.|
|[analysis_variant.py](analysis_variant.py)|Preparing separate Analysis run that does not reuse existing analysis. No model calls.|
|[execution_start.py](execution_start.py)|Set the synchronous settings; actual steps → model; effort; operation; request number; synchrony number before running to stdout; pipeline.log.|
|[analysis_restart.py](analysis_restart.py)|Stop; process end; evaluation completed; verify → save the entire previous analysis → terminate the request for a new model of the same input. No call for the model.|
|[analysis_sequence.py](analysis_sequence.py)|Analysis only run; state update in the approved order of pipeline.py analysis-sequence. --after-analysis-run starts after all the COMPLETE of the pipeline analysis·full_pipeline has been verified. Failed; uncertain pipeline does not automatically re-open and there is no Evaluation re-open.|
|[execution_control.py](execution_control.py)|Select run of A02/A03/A04 Resume-analysis retains the end-confirmed stop request response as uncertainty and Analysis waits only deactivate. Retry-analyses-requests only deactivates the end-Confirmation; IDs are deactivated only once approved at the time of designation and other requests are retained.|
|[run_layout.py](run_layout.py)|It's a new input/evaluation/analysis path and a previous runway.|
|[run_documentation.py](run_documentation.py)|Create a step-by-step input, output, file, usage, and read order with the README template. The default default settings for the root usage and run output_budget, the extension conditions, and record location are updated in the current guide and the defined template attached to the run is preserved.|

## Readme creation and renewal

In the static source-stage project roots, `PYTHONPATH=src .venv/bin/python -B src/finarch/documentation/manage.py refresh` After. `validate`Check that the actual preparation, collection and reporting that is not running `run_documentation.render()`It's created in a storage state and template, and the document update itself doesn't create a model call.

```mermaid
flowchart LR
 subgraph CONFIG["90-operations/settings.py"]
  C1["C01 load: default hyperparameter / read the specified config"] --> C2{"C02 Gemini level / Orca equatorial model OFF / max"}
  C2 -->|On · Support level of the model| C3["C03 Setup ready to return"]
  C2 -->|OFF: support level| FAIL["Run generated before error"]
 end
 subgraph STORE["90-operations/storage.py"]
  S1["S01 Configuration: read the config"] --> S2["S02 The run ID matches the star's cache approval connection"]
  S2 --> S3["S03 Returns the operating settings by model"]
 end
 subgraph VARIANT["90-operations/analysis_variant.py"]
  V01["A00.V01 Completed Evaluation Tag checked"] --> V02["A00.V02 Evaluation identical copy of the original hash"] --> V03["A00.V03 New run without the existing analysis."]
 end
 subgraph STARTUP["90-operations/execution_start.py"]
  L01["A00.L01 Read the synthetic real model effort"] --> L02["A00.L02 Work, request, and simultaneous output"] --> L03["A00.L03 Python/LLM step run"]
 end
 V03 --> L01
 subgraph RESTART["90-operations/analysis_restart.py"]
  R01["A00.R01 Stop, pay, evaluate the test"] --> R02["A00.R02 Previous analysis full-length"] --> R03["A00.R03 New config. New request for synchronized input 0entries"]
  R01 -->|Fail| RF["Keep the original file. Returns the current"]
 end
 subgraph SEQUENCE["90-operations/analysis_sequence.py"]
  Q01["A00.Q01 List of approved runs; current PID; post-report registration; if the prefix is not specified, the first run proceed immediately"] --> Q00["A00.Q00 When the forward run is specified, the analysis·full_pipeline all wait until the complete"] --> Q02["A00.Q02 Evaluation completed; stop analysis verified"] --> Q03["A00.Q03 Run the Analysis pipeline"] --> Q04{"A00.Q04 Result"}
  Q04 -->|Complete| Q05["Real completed record. Next run"] --> Q02
  Q04 -->|Error: Uncertain| Q06["The original recording is preserved."]
 end
 subgraph DOC["90-operations/run_documentation.py"]
  D01["D01 Render: Save config. state. Runtime output_budget read"] --> D02["D02 Insert the current route usage"]
  D02 --> D03["D03 Step template + create README in real state"]
 end
 subgraph CONTROL["90-operations/execution_control.py"]
  C01["A00.C01 pause: the runtime is closed; part output is saved"] --> C02["A00.C02 Resume-analysis: approval, weighting, evaluation completed confirmation"] --> C03["A00.C03 Unknown attempt preservation;Analysis only atmospheric undo/model call 0entries"]
  C02 -->|Running: The winner| CF["Rejection of the renewal"]
  C03 --> C04["A00.C04 Retry-analysis-requests: Conclusion manifest; corrected ID; completed verification; once re-release authorization"] --> C05["A00.C05 LLM: Approved ID only call-in and check-in"] --> C06["A00.C06 Full state re-order; other errors and misspellings request preservation"]
  C04 -->|Missing ID: Unidentified| CF
 end
 C03 --> Q03
 T["Current use: Stage README template"] --> D02
 T --> D03
 D03 --> O["Run root. Each step is README"]
 F["The output of the run is defined by the prompt schema."] -.->|Not to be corrected| D01
```

The DOC's sequence is document creation. STARTUP releases information just before the execution, and the Analysis sequence execution calls the LLM step of the pipeline in question. Python processes that are already running don't automatically load new functions, so they don't override the experiment to apply the code change.
