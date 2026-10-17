# Project and experiment dashboard

The session-down of the project is to see the one-stop run first, and then down to the experiment number and the case if necessary. `viewer/dashboard`One of the servers8895It doesn't create HTML for every executable folder that you open.

1. [03-project](03-project/README.md): **Project status**You can see the full session signal list on the left and the progress step, preference check items on the right, the session and save during operation on a screen. The session and the actual parent and parent details are popped up.
2. [01-overview](01-overview/README.md): **The experimental complexity**Registered exp-006 I see the main data, the response time and the timing, the distribution of the data by condition.
3. [02-explorer](02-explorer/README.md): **The analysis of cases**We can look at the same data for questions, answers, and conditions.
4. [Running and real file flow](../../docs/03-dashboard/README.md): Check where you read each number and its relationship.

Running it from the project root.

```sh
./viewer/dashboard/start.command
```

[Open the project status](http://127.0.0.1:8895/dashboard/03-project/) · [Experimental complexity](http://127.0.0.1:8895/dashboard/01-overview/) · [Problem analysis](http://127.0.0.1:8895/dashboard/02-explorer/)

The current state of the project is **Recorded session of the local Codex**And this project is a **Save the run-text**And the task group on the left is the screen classification. `↳` Only the numbers and parentheses pop-up are based on actual creation records. The color of the session refers to in-service, in-contact, unfinished connection, period. The most recent request for the session pop-up is a user message summary, and the relevant unfinished item is the item read separately from the document/action state. `In progress`It's not that the codex is in a conversation turn and the model request is in a turn. 1I'll update it every time. `Refresh`You can check it immediately, and you can miss the Codex session on another host or something that hasn't been saved yet, so you can see the scope, view, and source links on the screen together.

The two screens of the experimental numbers are exp-006 It's the baseline. **Unguided Solving / Criteria-Guided Solving**, **Reasoning OFF / Reasoning ON**It does not combine the different executions into a function, nor does it interpret the formatting pass-through-digit matching-use existence as meaningful. [common.css](common.css)The two numbers are a common frame for the screen, and the project screen uses a star-responsive style, which is just reading data, not reviewing model calls or scores.

[Project status creation and verification record](../../reports/run/20260929-project-dashboard/README.md)And the existing number screen.](../../reports/run/20260923-experiment-improvement/04-validation/dashboard-checks.json)Read this. `src/finarch/documentation/templates/dashboard.md`It's generated from.
