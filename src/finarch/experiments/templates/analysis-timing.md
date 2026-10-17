# Analysis of the time record {run}

[Analysis guide to the book](README.md) · [Experiment Viewer](http://127.0.0.1:8894/?run={run}&tab=analysis)

State of play: {status}The view of the newest: {updated_at}.

The longest-running analysis process at the moment: **{bottleneck}**The stage in progress is a set of numbers.

|Processing|It's actually a remarkable time.|The number of times it's been completed.|In progress|Complete call center value|
|---|---:|---:|---:|---:|
{table}

## The order of reading and interpretation

1. This document shows the time of each step, and the table has the top step and the inner process, so you don't add up the whole row.
2. [timing.json](timing.json)is the same as the estimate with the processing in progress, the central value;95It's a hundredth of a second, and the viewer reads this file.
3. [timing-events.jsonl](timing-events.jsonl)It preserves the start and finish times of each procedure, the watch time measured in single-clock clocks, the failure and failure attempts.
4. The raw response of individual model calls and the existing `process.json`The silver in each step `calls`[General log](../events.jsonl)And then the execution sequence is recorded.

Simultaneous call times save time by counting overlapping intervals only once. The sum of each call time is a resource usage indicator and the total time is different. Model call time includes CLI-network-server processing, and cannot be determined separately from the provider's internal weather and inference time. Stop-overs without a record of termination are left as a metric.

The table is the sum of the measured runtime. It does not include the gaps from the end of the runtime to correction and reopening. The end times and the center values also include attempts that ended in rejection and failure, so it does not interpret only the processing speed of the valid response.

The existing evaluation collection separates analysis time. The collection time and code clearance time before connecting the time records is not included in the measurement. `src/finarch/experiments/templates/analysis-timing.md`It's generated automatically.
