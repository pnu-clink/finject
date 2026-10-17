# Fin-o1 completed data recovery

`[vllm] gpu-2`Check the completed stage. `experiments/pipeline.py recover-a100-stage`I recovered all the raw response and the delivery file.

|Model by model.|Collect the response|It's a remote format.|Check the local file hash|
|---|---:|---:|---:|
$rows

Remote format passing is not a valid answer judgment. In each model guide, we read the summary input, prompt scheme, raw response, copy, action record, and acquisition record.

- [8B The recovery log.](recovery-8b.log)
- [14B The recovery log.](recovery-14b.log)
- In the Codex File Viewer, you open this document and model-by-model README.
- Additional model call: 0The analysis didn't run.
- The storage location of the experimental results `reports/experiments-run`It saves the raw response and the cohesion request in the model-by-model folder.

This colored guy, `experiments/pipeline.py report-a100-stages`It's generated from the template.
