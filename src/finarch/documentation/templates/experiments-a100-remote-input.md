# $run_id — A100 Public experiment input

This folder is a public input package that's synced from the PC after hashing verification, and it doesn't start running the model by just passing the file.

- Common code version: `$code_release`
- Open input set SHA-256: `$input_digest`
- The actual input list. `sync-input.json`
- Receiving copy of PC run control: `pc-state.json`

In order of reading: `config.json` → `00_input/public.jsonl` → `01_evaluation/02_request/`The Prompt schema model manifest → E01 `a100-runtime.json` → After running E03 The model folder. `runtime-provenance.json`, `remote-state.json`, `remote-results/`.

private right answer: External recognition classification and analysis is stored on the PC.4 Form-testing and experiment viewer reflection are responsible for a common synchronization pipeline of PCs, not overlapping other maps of existing synchronous input and raw response.
