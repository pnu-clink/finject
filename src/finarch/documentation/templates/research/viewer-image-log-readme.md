# v0.26 Image display; HTML exporting verification record

2026-09-28 The existing v0 is based on user requests.26The SVG 2We added the items to the research tool to be displayed in the reader and embedded in the HTML. The image grammar that was already in the source code was a fix to the problem that was being displayed as plain text, and we didn't rewrite the paper content or the picture itself.

## Reading order

1. [Bloodle guide](../../../viewer/research/README.md): Use method; file responsibility; current processing flow
2. [Confirmed results](verification.json): Actual performed display, download, offline, or stream processing verification
3. [Examples of HTML including images](../../../outputs/research/20260928-image-export/20260924-paper-draft-research.html): Copy made with the actual button download
4. [Operating log](events.jsonl)And [to change the original image](source-hashes-before.json): Change scope and data retention

|File|Role|
|---|---|
|before-index.html|Before changing the viewer source cache; or any running viewer|
|before-viewer-readme-template.md|The template before change.|
|verification.json|The actual verification results and the extent to which we didn't verify it directly|
|events.jsonl|Time-containing cause, change, and confirmation records|
|source-hashes-before.json|Research paper 5and SVG 2Before the change of items|
|viewer-overview.png / viewer-detail.png|The overview and the overview shown in the verification browser|
|offline-overview.png / offline-mobile.png|Internet without JavaScript containing yearly images HTML|
|offline-mobile-original-size.png|The offline mobile screen is enlarged to the original size and scrolling through the image area.|

The source of the data is now read by the stars in Chromium. 5I checked the items's offline download heater.26The SVG 2The items's internal bytes were the same as the original, and the offline markings were not JavaScript-free.390px The cross-screen navigation bar was passed, locked during image loading, delayed image response ignored from previous selections, error detection and recovery of file failures, incorrect formatting, and damaged SVG, and the mobile navigation of the long text path that was first discovered was supplemented by a downturn, and the failure record and re-validation results were left in the log.

The user screen is [research resource viewer](http://127.0.0.1:8896/viewer/research/) One is that you don't create any results screen in this folder, you don's change text, image originals and experimental responses, or call models, and because access to the browser in the app is not allowed as a policy verification failure, you can distinguish between direct verification of the screen being run and verification using a project file.

This README is generated from documentation/templates/research/viewer-image-log-readme.md.
