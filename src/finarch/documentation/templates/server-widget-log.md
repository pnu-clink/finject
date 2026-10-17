# The server widget running record

This folder is a fin-arch server widget.](../../apps/server-widget/README.md)It preserves actual execution and verification records, separate from the server's raw response and storage data.

|Reading order|File|Meaning|
|---|---|---|
|1|[smoke.log](smoke.log)|Before port order changes, start, reuse, restart, re-interface, other process protection, open the off server.|
|2|[port-order.log](port-order.log)|Data set → experiment → dashboard → research resource order, server start at new port|
|3|[build-and-install.json](build-and-install.json)|Release app tracking, identification, performance and letter checks|
|4|[current display renderer](preview.png) · [No response to the state render](experiment-unresponsive-preview.png)|Check the SwiftUI screen and the recoverable status button placement.|
|5|[default-ports.log](default-ports.log)|Each of them. `start.command`Identify the default port and server response to verify|
|6|[events.jsonl](events.jsonl)|The status of the widget is verified. Start, middle, heater, visual, service, port, result.|
|7|`experiments.log`, `dataset.log`, `dashboard.log`, `research.log`|Standard output and error for each server. If the file is not present, the server is not running on the widget yet.|
|8|[node-path-repair.json](node-path-repair.json) · [Figure](experiments-node-path-repair.png)|Reproduce, fix and realise Node browsing errors in the menu bar environment 8894 The recording of the screen check.|
|9|[First recovery record](unresponsive-recovery.log) → [Recorded by the Rev.](unresponsive-recovery-attempt-2.log) · [Compulsory closure check](forced-stop.log)|Record of preserving the experimental server response interruption and general shutdown failure, and verifying safe restart, other process protection, and enforcement shutdown paths|
|10|[unresponsive-recovery.json](unresponsive-recovery.json)|PID port after recovery, other server storage, app verification scope|

The actual current status is verified by prioritizing the widget's color points and server response over the last row of logs.](../../apps/server-widget/README.md)In this, you can check the meaning of the button and the color. `src/finarch/documentation/templates/server-widget-log.md`It's generated from.
