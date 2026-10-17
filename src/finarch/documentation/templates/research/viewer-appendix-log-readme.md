# Data creation add-ons and studies view the character size sort

2026-09-28 User request: from the paper 4.2·4.3It provides the entire logic of the summary data creation as an appendix, and it sets out the irregular size and large graphic description of the text under the title.

## Reading order

1. [Discussion v0.27](../../../reports/run/20260924-paper-draft/PAPER-KO.md)The following is the list of the additions B or [additional edit](../../../reports/run/20260924-paper-draft/DATA-GENERATION-APPENDIX.md)is read.
2. [File order is also available](../../../reports/run/20260924-paper-draft/DATA-GENERATION-FLOWS.md)Come on, Minister of the Interior.](../../../reports/run/20260924-paper-draft/DATA-GENERATION-EVIDENCE.json)In the current implementation, the case-control and confirmation times are contrasted.
3. [Public research viewer](http://127.0.0.1:8896/viewer/research/#s14)From the Hungarian paper v0.27Select or [check out the HTML copy](../../../outputs/research/20260928-appendix-typography/20260924-paper-draft-research.html)It opens up.
4. [Confirmed results](verification.json)[Working log](events.jsonl)It's a difference between a file check, a split browser check, and user-direct verification.

## Changes and file roles

|File|Role|
|---|---|
|before-index.html, before-runs.json, before-README.md|Viewer Fixed the file|
|verification.json|Subject-specific text tables, captions, order, downloads, offline checks|
|events.jsonl|Change, confirmation, failure and replacement order|
|typography-desktop.png, typography-mobile.png|3.5 Check the same size of the first paragraph and the subsequent paragraphs|
|figure-desktop.png, appendix-desktop.png|Picture captions and add-ons check screen|

Just the first step. 19pxThe rest of you. 16pxI removed the rule that I set to text and tables, and I inherited the size of the top text, and I left it on the desktop. 17pxMobile, and mobile. 16pxThe title is kept a separate size and the detailed description of the picture is 15px I've also fixed the ordering problem that was adding the table of subtractions to the subtraction, and I've supported the link and the code tag, so you can find the actual base of the addendum.

## Check the range

It currently uses a screen-out-check that provides the files as input from a separate Chromium. It distinguishes them from actual localhost services or user browsers, and does not claim user authentication completion. The HTML to be checked is stored only under the outputs. It does not create a separate viewer for each reports/run.

Experimentation, Creation, Evaluation, Analysis, Model Calls are not performed. The paper results and conclusions, RQ, SQ, H and the existing drawing originals are maintained. This README is generated from documentation/templates/research/viewer-appendix-log-readme.md.
