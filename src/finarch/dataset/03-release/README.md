# Selection and transmission of results

[Step of the letter: yoga; action flow](../../../../docs/01-dataset/03-release/README.md) · [A whole source structure](../../../../docs/01-dataset/90-operations/05-source-layout.md)

This folder owns the execution code for the documented stage. Output paths follow the existing run contract.

|File|Role|
|---|---|
|[export_run_results.py](export_run_results.py)|Now we're going to combine the output into JSON by type. `prepare_copy()`/`--prepared-output`The results already collected are new. `data/prepared` After checking the hash in the folder, you copy and send the manifest log template README. The source run is saved.|
|[concat_results.py](concat_results.py)|Check the hash ID of the two copies and then you can get the entire source. 8And then you replace it with the file. 7All types are PASS, select the source run map logs in the new folder and do not call the LLM.|
|[export_policy.py](export_policy.py)|The current variable excludes Reject-Exclude, the original excludes the entire, Generation excludes the type, and distinguishes it from automatic FAIL-Pending.|
|[publication/consolidate.py](publication/consolidate.py)|After the end of the entire generation, the actual source code in the data/generated;7It generates a single type of JSONL manifest log readme. 7It shows the type selection conditions.|
|[publication/schema.py](publication/schema.py)|The original.7It verifies the type structure and content hash, the ID-input hash connection of the ratings.|
|[edit_provenance.py](edit_provenance.py)|Source→VALUE→SOURCE Edit the file and check the current Q/C chart.|
|[external_knowledge.py](external_knowledge.py)|It only records the type of external information that meets the verification requirements, the actual use and requirements.|
|[original_baseline.py](original_baseline.py)|Prepare original Q/C only; never execute a baseline or import its runner.|
|[response_screen.py](response_screen.py)|Explicit, immutable-input first-repeat screening. No provider calls.|
|[review_first_repeat.py](review_first_repeat.py)|Explicit v2 entry point. Import never reads or writes legacy review artifacts.|
|[source_pair_review.py](source_pair_review.py)|Match each frozen SOURCE to its saved VALUE dependency; no generation or API calls.|
