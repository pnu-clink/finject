# {run_name} • Combined production results

In order of reading: `manifest.json` → `00-input.json` → `01-...json`through `07-...json`The original file is {count}And the row count is in the manifest, instead of the row position. `id`So we connect the original to the transformation.

**Export rates:** {export_policy_note} The PASS of the experiment.7The type completion requirements are not the same. The original generated file, judgment, and pass parameters do not change.

- `00-input.json`: Preparation input and current state. `input`And that includes the private standard.
- The original line. `external_knowledge`is a private production classification. `used=true` **Final Preparation PASS is now available.**, external types recorded with actual use on the correct path of the calculation graph, and `05-verification`Only if the PASS and EXTERNAL requirements are all matched. `used_types`There is a corresponding `EXTERNAL_RULE`/`EXTERNAL_DATA`And I'm recording it. `used=false`, `used_types=[]`And this is `false`It's not a proof that you didn't write out the external information, but a proof that the validation conditions are not satisfactory. It doesn't confuse the use declaration of the previous flaw with the necessary assessment of the validator.
- `01`~`07`: Type-by-type final storage status and Q/C generated. `source`The actual generated phrase file, `result`is the type of variable folder.
- Each row is `edit_provenance`: source → value change → source additional order, step by step source location; pre-replacement string; color separation `segments`It's a Q/C hash and a build comparison file path hash.
- `status=PASS`I passed the automatic test. The approval of the person or the meaning of the correct answer is unknown.
- `status=FAIL` Or `NOT_EVALUATED`It's stored together when there's a Q/C generated. It's not automatically included in the experiment input.
- `status=NOT_RUN`There's no record of the syntax or the syntax being created. Pre-stage transitions and phrases that weren't explicitly rejected are also on the list.
- `manifest.json`: row count of each file256The original Generation results report of the SHA-256.
- `export-log.json`: abstract visual; resulting numbers and the actual basis of external classification paths; SHA-256If the metadata is missing, it's only the accepted input of the same Q/C. `reference_metadata_repairs`The original data.json does not change. If you only reinforce the change in the existing results `edit_provenance_revisions`In the past, the result of the merging left the external hashing of the file after the internal storage. `external_knowledge_revisions`left a visual, ginger, post-exposure hash and the original `00-input.json` bytes `revisions/`It's not considered a classification that existed since its creation.

The default settings for the new experiment require this folder to be required. `PASS` It's a Q/C of a line and a precision of the original that makes it a finished public model input.`edit_provenance`·`external_knowledge`When you pass this classification to the Analysis of the experiment, you don't put it in the public Q/C. precision. The separate settings that reuse the abstract input of the previous experiment bypass this path, so you can't combine it. The files in the original run folder are preserved.

The order of reading: the original row → the same ID's modification → `edit_provenance.steps`The IC-source reads the IC-value position of the first step from the original C, and the source position of the second step. **Added the value phrase to C**The location of the Unicode character unit is `[start, end)`So you don't combine the two steps into the same standard position.

|Change the power.|The intent and the viewer processing|
|---|---|
|VERIFIED|If you apply the saved edits in the order they are, they match the final Q/C. The value sentences are green, source A is pink, source B is red.|
|UNAVAILABLE|No Q/C or editing record unverified. Not displayed as unchanged|
|MISMATCH|Standard elementary, high, post-string, hash, recover result inconsistency.|

`VERIFIED`The deleted string is only an edit record, and not a correct answer or human approval. The deleted array is only an editing record and not put back into the actual model input C.

Reproduce command: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m finarch.dataset.03-release.export_run_results reports/run/{run_name}`

Change power reinforcement that maintains the existing Q/C status: same command `--edit-provenance-only`attach

The existing Q/C status;7External use sorting supplement that maintains the type file: to the same command `--external-knowledge-only`This is a Python process that reads the saved creation records and does not call the model back.
