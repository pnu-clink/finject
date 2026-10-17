# Ready to enter.

## Start the program.

FinanceReasoning is the launch program for the entire distribution `full_finance.py`So, depending on the type of source, you select the existing entry point below.

|Subject to input|Start the program.|Human Trafficking|
|---|---|---|
|FinanceReasoning is full|`src/finarch/dataset/00-input/full_finance.py`|`--catalog`, `--output`. easy → medium → hard source hashing check. Outsourced. Generate the input|
|TAT-QA is the whole|`src/finarch/dataset/00-input/tatqa_full.py`|Receiving the output folder as a location factor. `config/source-catalog.json`The use of the TAT-QA source|
|General sample ready|`src/finarch/cli.py prepare` → `00-input/build.py`|`--sources`, `--output`, `--seed`, `--total` Or `--per-source`|

Run it from the storage root. `PATH_TO_...`It's a location indicator that you need to change to the actual path, and it specifies a new output folder.

```sh
PYTHONPATH=src .venv/bin/python -B -m finarch.dataset.00-input.full_finance --catalog PATH_TO_FINANCE_CATALOG --output PATH_TO_NEW_INPUT_FOLDER
```

The entire Finance catalogue is `finance-easy`, `finance-medium`, `finance-hard` The three sources should be in order. If you give the list of sources, including TAT-QA, as it is, you're rejected. `--hyperparameter PATH_TO_HYPERPARAMETER_JSON`Add the number of the number. `input.source_prefix`Choose the source. `input.id_map_path`It preserves the raw_id → id correspondence of the existing input. `input.expected_count`The source Q/C/A is now read as a new adapter and the previous LLM results are not reused.

Inner route: Select the source `adapters.py` → `content.py` So if you want to get a JSON text, `json_context.py` → Check the input scheme `data/prepared/...` outputs. `check_json_contexts.py`It's not a screening tool and it's not the starting point of production. 01And then there's the finished `input.json`It's transmitting.

[Top: The whole production.](../README.md) · The following: [Preparation](../01-preparation/README.md)

So we're going to sort the source data into the common input before the meaning verification, and the fact that we're prepared to enter doesn't mean that the exact answer to the case is verified.

|In order.|Detailed documentation|Content|
|---|---|---|
|IN.01~04|[Repair and preservation of original](01-selection.md)|Source hash → path selection → common Q/C/A → input, output, and completion record|
|IN.03.J|[JSON text tables are converted](01-selection.md#json-%EB%B3%B8%EB%AC%B8-%ED%91%9C-%EB%B3%80%ED%99%98--in03j)|JSON object; table string arrangement → table; band → value; free form; source position contrast|

FinanceReasoning distinguishes the selection conditions for the entire, TAT-QA-wide, initial sample path. The specific quantity is in the input bundle manifest. The source is data/raw, the production input is data/prepared, the actual execution is verified in reports/run.
