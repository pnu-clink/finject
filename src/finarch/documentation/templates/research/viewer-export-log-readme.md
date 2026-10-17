# Research paper HTML output changes; verification records

2026-09-28 At the request of the user, we added the HTML output of the selected document to the research resource viewer.

## Reading order

1. [Review of the research](../../../viewer/research/README.md)Use and implementation flow
2. [Confirmed results](verification.json)Downloads, offline display, data transfers, stream processing and verification limits
3. [Operating log](events.jsonl)Change and confirm order
4. [Trying to change the original](source-hashes-before.json): Research paper conservation criteria
5. [Examples of a Han Chinese paper I showed you](../../../outputs/research/20260928-html-export/20260924-paper-draft-research.html)A validated copy made with a real button download.

|File|Role|
|---|---|
|before-index.html|Before changing the viewer source copy; or no executable viewer|
|before-README.md|I'm not going to change the viewer.|
|before-viewer-readme-template.md|I changed the README template copy|
|verification.json|The actual verification and the remaining limits|
|events.jsonl|Change and confirmation records with time|
|source-hashes-before.json|5Before the change in the items research paper, SHA-256|
|viewer-desktop.png / viewer-mobile.png|The check-in button and the data screen in the verification browser|
|offline-desktop.png / offline-mobile.png|Exporting files without Internet JavaScript|

The source of the data is now read by the stars in Chromium. 5We checked the actual downloads, text, tabs, offline openings, traffic movements of each items, button locks during data loading, ignoring previous responses that arrived late, and rebooting after a scan failure and output error. The browser connection in the app was not directly verified as an initialization error, and does not show that the server screen is currently running.

The user screen is [research resource viewer](http://127.0.0.1:8896/viewer/research/) One of them is that you don't create a result screen in this folder, you don's rewrite the output or run an experiment, and this README is generated from documentation/templates/research/viewer-export-log-readme.md.
