# Save run from the dashboard to the taskbar in the project scenario

[Full article in German](../README.md) · [Source structure](../01-dataset/90-operations/05-source-layout.md) · [screen run](../../viewer/dashboard/README.md)

Display name: **Unguided Solving / Criteria-Guided Solving**, **Reasoning OFF / Reasoning ON**and does not include an abbreviated name.

The dashboard consists of a project screen that reads the local session, a cache run, and a document, and two screen numbers stored in the experiment.006 is the baseline and is not combined with other rounds.

|Stage|Responsibility file|Input → output|
|---|---|---|
|DB01 Data connection|[01-data/data.py](../../src/finarch/dashboard/01-data/data.py)|Registered report, request, conclusion, hash, problem connection, meeting cache|
|DB02 Figure extraction|[02-metrics/metrics.py](../../src/finarch/dashboard/02-metrics/metrics.py)|Primary records → processing time, perception, token cost, unrecorded is null|
|DB03 Server|[viewer/resources.py](../../src/finarch/dashboard/viewer/resources.py), [server.py](../../src/finarch/dashboard/viewer/server.py)|Allow URL; trial ID; see the documented source code → JSON or screen file|
|DB04 Showing|[Some of the events](../../viewer/dashboard/01-overview/README.md)[Problem analysis](../../viewer/dashboard/02-explorer/README.md)|Internal conditions stored: number → official name mark; filter; chart; answer chart; question detail|
|DB05 Collecting projects|[03-project/monitor.py](../../src/finarch/dashboard/03-project/monitor.py)|Local Codex session DB; directory run/text → session; parent child; most recent request; incomplete; status JSON|
|DB06 Project visit|[viewer/resources.py](../../src/finarch/dashboard/viewer/resources.py), [server.py](../../src/finarch/dashboard/viewer/server.py)|`/api/project/status`Allow the original. `ref` → JSON or text, misused 404|
|DB07 Project sign|[03-project](../../viewer/dashboard/03-project/README.md)|JSON → Left full session signal list; Right progress stage/unfinished/in operation/actions/section by session recent 3Build and actual create a relationship pop-up-round link|

```mermaid
flowchart LR
 subgraph data["dashboard/01-data/data.py · Python"]
  A["DB01.1 Check the registered source and area"] --> B["DB01.2 Save the file, decrypt, and reply"]
  A -->|Out of the way.| X["DB01E error of inspection"]
 end
 subgraph metrics["dashboard/02-metrics/metrics.py · Python"]
  B --> C["DB02.1 Recorded numbers, extracted observations"]
  C -->|Missing vision| N["DB02.2 null-containment"]
 end
 subgraph server["dashboard/viewer/resources.py · Python"]
  C & N --> D["DB03.1 Allowed browsing API"]
 end
 subgraph pages["viewer/dashboard/01-overview·02-explorer · JavaScript"]
  D --> E["DB04.1 Internal conditions → official naming, situation, problem comparison"]
  E -->|Refresh| A
 end
```

Each box is a real liability file, and this stream has no automatic recoveries of LLM calls, credits, failures. 0The denominator of the operating index is the source log link to the [existing detailed operating document](../02-experiments/README.md#%EB%B7%B0%EC%96%B4%EC%99%80-%EB%AC%B8%EC%84%9C-%EA%B4%80%EB%A6%AC)Check it together.

## The actual order of the project's progress.

```mermaid
flowchart LR
 subgraph monitor["dashboard/03-project/monitor.py · Python"]
  M1["DB05.1 Read local session DB"] --> M2["DB05.2 Project session: most recent request maximum 3entries"]
  M1 -->|DB No. The company failed.| W["DB05E.E. Empty session and warning"]
  M2 --> M3["DB05.3 The actual parent-name of thread_spawn_edges"]
  R["DB05.4 Save run. Read the unfinished document"] --> M4["DB05.5 Step-by-step, work together"]
  R -->|No data| U["DB05Keep your memory."]
  S["DB05.6 Local server response verified"] --> M5["DB05.7 Current view and JSON"]
  M3 & M4 & U & W --> M5
 end
 subgraph server["dashboard/viewer/resources.py · server.py · Python"]
  M5 --> A["DB06.1 Status API: Reference provided by the document"]
  A -->|Ref not allowed| X["DB06.E 404"]
 end
 subgraph browser["viewer/dashboard/03-project/project.js · JavaScript"]
  A --> P["DB07.1 Project screen: nearby link display"]
  P -->|1Read the new part.| M1
  A -->|Read error| E["DB07.E warning and reset sign"]
 end
 classDef detail fill:#fce4ee,stroke:#c75d81,color:#442035;
 class M1,M2,M3,R,M4,S,M5,W,U,A,X,P,E detail;
 style monitor fill:#e8f1fa,stroke:#5b82aa,color:#19304a
 style server fill:#e8f1fa,stroke:#5b82aa,color:#19304a
 style browser fill:#e8f1fa,stroke:#5b82aa,color:#19304a
```

The pink color is the actual detail of this document.5~DB07 And the color of the blue file box represents the boundary of code ownership.`subgraph`So this is the file limit. `In progress`The codex is in a conversational turn and does not interpret it as a running model call.](../../src/finarch/dashboard/03-project/session-map.json)And the screen classification is, **The actual parent-child relationship is a creation record.** It reads in the open issues, after-conference, and save run mode, and does not make a complete judgment as a user message. The session or pre-saving tasks of other hosts may not be visible.
