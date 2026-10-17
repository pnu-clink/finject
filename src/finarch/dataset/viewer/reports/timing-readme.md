# Running time and use of LLM

Running: `{run_id}`

1. `timing.json`Start-up: Start-up, finish-up view, total time taken, CLI command.
2. The number of each of the charts `timing.json`The complementary instruction writing includes the number of times the cause was collected.
3. `timing-report.json`: total; numerical; interval observation time, LLM call time sum; overlapping removal time, call number; token usage.
4. `log/cli.log`, `log/run/{run_id}/default.log`: `execution.run`, `execution.round`, `execution.timing_summary`One record is a JSON line.

The sum of LLM call times can be greater than the total course time because of parallel running. **The scope of LLM**It takes only one time overlapping, including CLI transmission time, and it's not the time of pure model inference, and it doesn't add up because the time of intersection and time of interpolation overlapping.

Additional functions before running `observed_event_window`The raw response and past timestamps do not modify. The raw response does not include the unrecorded start-preparation and completion interval, and does not display the exact full CLI time.

[Time and volume viewer](http://127.0.0.1:8893/?run={run_id}&round=01-round&case=test-0001&tab=dtt)in **Time and LLM usage** You press the button, and you see a whole cross-sectional bar and a cross-sections chart on the same screen.
