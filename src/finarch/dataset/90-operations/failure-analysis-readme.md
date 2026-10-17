# Failure analysis

In order of reading: `job.json` → `snapshot.json` → `The following is a list of items/<br><br>/<br />/result.json` → Each LLM `01-input`, `02-raw-response`, `03-result`.

- job.json: Object, model, and interpretation approved in the verification window.
- snapshot.json: The analysis time specifies the source, the QCA of the file, the step output, the code graph, the verification, the actual feedback application record and the file hash.
- items: English source analysis and Korean screen translation. The base ID is connected to the actual storage file of request.json.
- queue.json / scheduler.log: Failure to interpret the progress mode of the existing preparation/generation scheduler record.
- API-usage: The actual token, the average per call, the estimated cost per storage unit, including the failed API response, to distinguish it from the actual bill.

If you select the run in the viewer, the entire folding table below the chart guide will appear on the human-review screen, and if the margin of the target output is changed, it will be shown as past interpretation. `.ref.json`It's not the same interpretation, it's not a judgment or feedback from the next loop, it doesn't change the current run, pain, failure, and status of the log.

Analysis 1Turn, mark translate 1The turn is the maximum number of calls. There's no automatic reset, and individual failures don't stop the rest of the analysis. Only translation fails to preserve the English analysis.
