# PC ↔ A100 Experimental synchronization

State of play: **$status** · Check-in time: `$updated_at` (UTC)

Common code hash: `$code_release`

A100 Path of work: `$remote_workspace`

## Reading order

1. [status.json](status.json)Code: public input matching, run-by-run receiving state, error.
2. [events.jsonl](events.jsonl)Periodically check visual; code version; fail record.
3. [process.json](process.json)Sync process PID: Preview visual cycle. It doesn't judge that PID files are running.
4. By model. `*-remote-snapshot.json`: Complete response hash, server run status, option record, released by the server.
5. By model. `*-received.json`: Actual response hash and change detectable file information verified on PC.
6. [verification.json](verification.json)Local inspection, server verification, actual collection verification scope and mismatched items.

The common experimental view of the **PC ↔ A100 Synchronizing** The same status.json is checked on the screen.3 `sync-status.json`This synchronization does not run model call evaluation complete judgment analysis.

Code and public input PC → A100So, the state and the raw response is A1.00 → is a PC. private correct answer. External recognition classification. Analysis does not transmit. Other charts of existing experimental input and raw response are recorded in a collision without overwriting. New code releases are applied to the next execution and do not change the code of the process being executed.

The stop-and-go state of the PC is to check each turn, separate from the change in code or public input, and to change the change in the current state of the computer. `pc-state.json`The common runner reads the stop state of this file and stops sending new requests. It's not a function to cancel requests already sent from the previous runner.

In the first test, we calculate the actual file hash. Then we use the previously published raw response hash list if the number of completed rows in the remote run is not changed.`UNCHANGED_EXECUTION_PUBLISHED_HASHES`On PC, we're going to scan the raw response of the file information again. `--sync-force`It re-verifies all the raw response bytes on the remote and PC, distinguishing between the range of periodic checks and the full range of re-checks.

Running: `PYTHONPATH=src .venv/bin/python -B -m finarch.experiments.pipeline a100-sync --sync-action cycle`

Cyclic execution: same command `--sync-action watch`Stop: This is the folder. `STOP` If you create a file, it'll shut down after the current loop is over.
