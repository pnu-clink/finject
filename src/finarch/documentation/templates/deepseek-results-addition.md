# DeepSeek results added

Existing 20261008 And then you add the DeepSeek results to the paper's data. 0It's a building that preserves the existing experimental files and the existing model set.

1. `deepseek-summary.json`: support rate of additional models, source correspondence pair, recovery probability comparison.
2. `summary.json`The result of a combination of the existing snapshots and the additional models.
3. `manifest.json`: input path; interpretation and verification results.
4. `responses.jsonl`: Planned response of additional models 43,328The original response and the judgement path refer to the existing run.
5. `execution.log`The verification and collection of the stored results. The actual model execution dynamics are in the original run.

The original unit judgment 1,354of {valid:,}The plan is to change the response. 37,912The verdict is over. {reviewed:,}That's the unreviewed output. {failed:,}That's the result of an uncertain verdict. {pending:,}The denominator is the same as the original paper, and the restoration comparison is the original unit of the original record of the restoration. 10,000Re-seed 20261009I'm using the .

[Existence experiment viewer](http://127.0.0.1:8894/?run={run_id}&tab=answerable)You can check the raw response and the judgement.
