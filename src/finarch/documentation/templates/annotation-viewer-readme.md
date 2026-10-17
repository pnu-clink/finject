# Annotation Screen source

[Located usage guide](../../../annotation/README.md) · [Production Viewer](../README.md) · [Requirements and actual flows](../../../docs/01-dataset/90-operations/04-viewer.md).

|File|Input → process → output|
|---|---|
|[index.html](index.html)|Date: Date set: File selection → Data set highlight: Homepage: Prior success: Prior success list: Type checkbox: Bypass template: Copy at the bottom of a row Manager input/right store|
|[manager.js](manager.js)|Current Annotation data → Date-to-date comparison switching; success space type display; n-name determination; current filter/search maintenance in V; display type within the move; presence list maintenance → comparison screen; result JSON·G02 The new tab.|
|[reviews.js](reviews.js)|Enter a row below the active case, type, administrator record →2/3 Storage focus;4 Input focus, type-specific drawing, operation store, correction, record unfolding, list checkbox, HTML/ZIP download|
|[reviewer.html](reviewer.html)|Request to send out; authenticated assessment; verified full text; read inline material; single template; search without server connection; type selection; Q/E move|
|[style.css](style.css)|7items type and name evaluator 100% The writing, the source, the reviewer. 40%/U.S.A. 60%• Preview of the type/condition of the tax;38px Key input: Red/yellow markings specified → PC specific layout/use of the page scroll|
|[normalize.py](../../../src/finarch/dataset/viewer/annotation/normalize.py)|Actual 2Export contract → Determinable format supplementation; specified dataset/actual metadata storage → supplementary copy; change prefix; misresolved error|
|[agreement.py](../../../src/finarch/dataset/viewer/annotation/agreement.py)|Problems: type: evaluator: time run → one year comparison range connection to the only distribution model; common storage judgment contrast → Cohen/Fleiss κ; uniformity rate; denominator|
|[store.py](../../../src/finarch/dataset/viewer/annotation/store.py)|annotation/date of JSON → original hash; date-by-date comparison list removal of overwriting; independent supplementary copy; log; readme → current results reading single screen|
|[sources.py](../../../src/finarch/dataset/viewer/annotation/sources.py)|The source source, the syntax, the edit source type, the source base.|
|[links.py](../../../src/finarch/dataset/viewer/annotation/links.py)|The problem of choice. 7Type → save edit; whole text; numerical contrast → G02 URL or reason for not identifying|
|[reviews.py](../../../src/finarch/dataset/viewer/annotation/reviews.py)|The type of selection 3The following are the main requirements for the search engine: search engine, search engine, and search engine.|
|[review_export.py](../../../src/finarch/dataset/viewer/annotation/review_export.py)|Receiver request template → secure inline JSON insert → independent HTML|
|[G02 comparison.js](../prepare/generation/common/02-generate-text/comparison.js)|The same problem-type stored G02 Original text → complete comparison → direct link to the text location move|

The server is [dataset/viewer/server.py](../../../src/finarch/dataset/viewer/server.py) `/annotation/`, `/api/annotation`·`/api/annotation/catalog`and dedicated files, new records, and records;`/api/annotation/g02`·`/api/annotation/manager-review`·`/api/annotation/review-files`·`/api/annotation/review-export` It's a path. It applies the existing loopback-origin checks to register and administrator storage. `src/finarch` The screen doesn't call the copy-making-decision-storage API, the HTML for transmitting is when you download it and you put the data in the template and it's a source that doesn't have input itself.
