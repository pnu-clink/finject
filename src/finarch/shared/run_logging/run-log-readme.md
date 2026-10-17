# Running logs

Running: `{run_id}`

All of them. `.log` The file is JSON Lines. `\n`So one record is a physical line.

| File | Content |
|---|---|
| `../../cli.log` | Just before the actual CLI starts, we're going to separate the execution from the argv. |
| `pipeline.log` | Start the call of an important function. There is no input or internal function detail. |
| `detail.log` | Detailed records with function names in JSON key, including request, response, output content, failure, time. |
| `llm-ic-value.log` | Creating and reviewing IC-VALUE |
| `llm-ic-source.log` | Creating and reviewing IC-SOURCE |
| `llm-ic-relation.log` | Create and review IC-RELATION |
| `llm-ea.log` | Create and review EA |
| `llm.log` | Four types of LLM records other than POT etc |
| `default.log` | Run all the rows recorded in the above file and save them together in full order. |

At first, `default.log`And if you look at the call flow, `pipeline.log`is read.
`function`And there's a key within the same name. `call_id`and `problem_id`So we're going to divide it into.
Overlapping internal processing is also searched for as a top-level function. `detail.log`The interior of `function`And then there's the actual internal function.

`grep -F 'dtt.realize' detail.log`You can find a detailed record of the function.

The dedicated viewer: http://127.0.0.1:8893/logs?run={run_id}
Run, select files, search for function names/text, open the input and output, 2It provides second-automatic renewal.
The files. `sequence`So in individual files, you can skip the number. `default.log`And it's going to increase in this order.
If the same record is on both the file details and the LLM file, it's also two rows in the integration log. `log` It's a field that separates which file is a record.

The record generates the actual call time, not replenish the unfinished call with success or fill it with past results.

## The same path as the output.

The step record is `test-0001/02-calculation/<function>/detail.log`Like the run output, it follows the phrase, step, function path. The raw response file storage events are connected to the log path that corresponds to the actual directory of that file. `artifact_directory`and `log_path`The resulting folder and log folder correspond to the log folder. `default.log`CLI is a common `log/cli.log`And it records.

Timestamp values use the system local time with milliseconds and a UTC offset (YYYY-MM-DD HH:mm:ss.SSS+09:00 on a Korean system). Existing raw records are preserved.

## The total order and time taken.

`execution.run`and `execution.round`The START/END has the actual argv-system time measured in local start/finish visual and time-contact clock. `execution.timing_summary`is a summary of the total course time and LLM usage. `production.continue_feedback`is the same runtime followed by the runtime command. `log/cli.log`And run it. `default.log`You can search it from here.
