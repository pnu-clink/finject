# 02 • A phrase analysis dashboard

The user's mark is **Unguided Solving / Criteria-Guided Solving**, **Reasoning OFF / Reasoning ON**I'm just using the internal condition value to keep the filter and the element log connected.

[High-level guide](../README.md) · [Previous: Complexity of the situation](../01-overview/README.md)

The short filter at the top and the left scoreboard at the top, the right raw response scoreboard at one screen. **Real time completed**So, the tax axis is **Response time**If necessary, it switches to the existing response time × output tokens. Select the point or row of tables, and then check the Unguided Solving/Criteria-Guided Solving response in cases like question, text, latest answer, explanation, usage. You can reduce the range to type, prompt, reference, form, status, check tag, problem search. `trial`You send the URL and it opens the response.

|File|Role|
|---|---|
|[index.html](index.html)|Condition filters, response scores, matching tabs, raw response details|
|[Common style](../common.css)|Header menu, color, font, filter, mark, panel, and so on.|
|[explorer.css](explorer.css)|Chart-chart-tax distribution of the case|
|[explorer.js](explorer.js)|Answer selection, filter, chart, tag, query, or text reading connection|

The response that doesn't have the visual, time, and token of the selected axis is the number that is excluded from the scoreboard and left on the table. 0It's not a token time to determine the accuracy or repeatability of the response, and it's not an existing score; it's a raw response.

[Figure opens](http://127.0.0.1:8895/dashboard/02-explorer/) · [Experimental Viewer of such an execution](http://127.0.0.1:8894/?run=20260920-exp-006&tab=analysis) · [Details of the description](../../../docs/02-experiments/README.md)

This README is a `dashboard-explorer.md` It's a template.
