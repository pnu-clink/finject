# Project status check code

[Deskboard running flow](../../../../docs/03-dashboard/README.md) · [Figure](../../../../viewer/dashboard/03-project/README.md)

|File|Role|
|---|---|
|[monitor.py](monitor.py)|Read the local Codex session DB and the stored document/actions status, and build the current status JSON.|
|[session-map.json](session-map.json)|It connects the identified main session ID to the task group, and it's not used as a basis for parent-child relationships.|

`load_project_data()`The codex records the path of the project and takes the path of a session, runs, unfinished, returns the server state. `BLOCKED`If it's stored, then the run is `state.json`Based on `Block it.` It creates an item. 0And then it turns it back on the screen and leaves a warning. `thread_spawn_edges`There's no model call or test run during the observation.
