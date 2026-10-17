# POT run-out testing and diagnosis

It's pre-verification code, not an approved output for the next step.

In order of reading: `01-response.json` raw response `02-program.py` Extracted source code `03-context.json` The text for verifying the evidence `04-execution/result.json` Running the quarantine `05-response-check.json` Answer checks including sources `06-summary.json` Two results summarized.

Python code is `fact()` And we're using the running environment, and we're actually using the running environments. `python 02-program.py`It doesn't run in the project root, and it uses the following command: OUTUT to designate a new directory that doesn't exist yet.

```sh
PYTHONPATH=src .venv/bin/python -B -m finarch.dataset.01-preparation.03-calculation.diagnostics --response PATH/01-response.json --context PATH/03-context.json --output OUTPUT
```

It keeps the number-text contrast, external database catalog verification, and OS isolation of existing Python runners. It preserves the isolation execution results even if the source connection check fails. Running success doesn't guarantee the source-gold unit. 03-We can see two results in the calculation.
