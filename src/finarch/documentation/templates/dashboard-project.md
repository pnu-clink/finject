# Project Status: Session and remaining work

[The entire dashboard is](../README.md) → [Open the project scenario](http://127.0.0.1:8895/dashboard/03-project/) → [From source code flow](../../../docs/03-dashboard/README.md) I read it in sequence. `./viewer/dashboard/start.command`Run the program.

|File|Role|
|---|---|
|[index.html](index.html)|The one-way indicator, the execution step, the session relationship, the task list, the server status position.|
|[project.js](project.js)|Read-only API requests, full session signal list; preferred task; action step display; session/project/organic relationship popups and 1minute refresh|
|[project.css](project.css)|Distinguishing between the desktop and the narrow screen|
|[monitor.py](../../../src/finarch/dashboard/03-project/monitor.py)|Implementation of Python reading the Codex local session and storage data|
|[session-map.json](../../../src/finarch/dashboard/03-project/session-map.json)|Key session task-by-screen sorting|
|[Created and verified records](../../../reports/run/20260929-project-dashboard/README.md)|Run logs, verification results, scope of interpretation|

The order in which you read it. **Left full session structure → Right creation, evaluation, analysis, research step → Priority check 6Previous and current work → Save run; business breakdown remaining → Server status**So we've moved the content of each session and the entire task to pop-up, so you can see the main structure without scrolling through the screen, and then the task group is sorted for convenience, and then you can see that the whole task group is pop-up. `↳`And the parent-name pop-up only shows if there's a codex creation record. **Green working / Red barrier connection / Yellow unfinished connection / Gray air**That's the most recent request for a session. 3This is not a list of tasks that are recent user input and completed. 3The item is the item that was verified in separate document-run state.

If the data is missing, you can give me a warning. `Not recorded`The session of the other host may not be in the local session record. `Source evidence`The screen doesn't fix the project data or call the model.
