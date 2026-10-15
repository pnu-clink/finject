# Bounded production feedback

One run contains 01-round, 02-round and 03-round. Later rounds exist only when failed cases need a retry. The initial round starts from prepared source inputs with fresh model calls. Each later round processes failed variants and any dependent variants invalidated by a changed value claim. Passing inputs from the same run are frozen snapshots, identified by inherited-inputs.json with hashes; they are not counted as new calls. No other run is reused.

The cumulative supplements live only in feedback/{target-role}/{type}.json outside rounds. Every round reads this directory, never a chain of previous guidance files. LLM requests preserve the exact common, type-specific and supplemental instruction parts with hashes. Feedback generation records include input failures, schema, raw response and merged cumulative output.

Read each round's 05-text/03-final-validator/03-result.json, then 05-text/04-LLM-build-feedback, followed by the next round's case stages. Final validation uses existing checks; it does not invent a new correctness judgment. First pass ends retry for that item. Three rounds is the hard limit. Failures remain visible. Infrastructure errors block the loop instead of being interpreted as text defects. Human review is prepared after loop termination, with decisions pending.

Logs mirror round/case/stage under log/run/{run-id}; default.log merges the entire run and each round has its own default.log. The central viewer selects the run and round; loop-summary.json records transitions and final case locations. Historical run records remain readable.

## Result report

In the viewer, open the result report after the three round counters. It compares completed validator snapshots by case and variant, with failure reasons, resolved failures, guidance changes, and upstream exclusions. Pending rounds are not counted as successful.

## 시간·호출량

`timing.json`은 실행 명령과 시작·종료·총 소요 시간, 각 차수 `timing.json`은 차수 시간입니다. 종료 후 `timing-report.json`과 `TIMING-README.md`가 생성됩니다. 뷰어의 시간·LLM 사용량 버튼에서 전체·차수·구간별 차트를 확인합니다. CLI 마지막 END/SUMMARY 및 `log/cli.log`에서도 확인할 수 있습니다.
